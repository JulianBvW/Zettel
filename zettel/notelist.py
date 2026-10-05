'''The list: every note, reachable without touching the mouse.'''

import time

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import config, notes  # noqa: E402

# 1 to 9, on the number row and on the keypad. Both runs are contiguous.
DIGITS = {}
for _index in range(config.NUMBERED_ROWS):
    DIGITS[Gdk.KEY_1 + _index] = _index
    DIGITS[Gdk.KEY_KP_1 + _index] = _index

# The key left of the 1, asked for by position rather than by character: on
# the US layout it sends `grave`, in the German group `dead_circumflex`. The
# keycode is the same either way, and the keyvals are only a way back in if
# the keycode ever is not.
NEW_NOTE_KEYCODE = 49
NEW_NOTE_KEYVALS = (Gdk.KEY_grave, Gdk.KEY_asciitilde,
                    Gdk.KEY_dead_circumflex, Gdk.KEY_degree)


class ListView(Gtk.ScrolledWindow):
    '''Every note on one screen, newest first.

    There is exactly one mark: the row under the cursor. It carries the blue
    tile and the lighter background, and it is what the arrow keys move. A
    second, separate highlight for "the note you last had open" would only
    compete with it for the same glance -- so the cursor simply starts there.
    '''

    def __init__(self, verbose=False):
        super().__init__()
        self._verbose = verbose

        # Set by the window. Plain callbacks rather than GObject signals:
        # there are two of them and they carry a Path.
        self.on_choose = None
        self.on_new = None
        self.on_delete = None

        self.rows = Gtk.ListBox()
        self.rows.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.rows.set_activate_on_single_click(True)
        self.rows.connect('row-activated', self._on_row_activated)
        self.rows.get_style_context().add_class('note-list')
        self.rows.set_margin_start(config.LIST_MARGIN_LEFT)
        self.rows.set_margin_end(config.LIST_MARGIN_RIGHT)
        self.rows.set_margin_top(config.LIST_MARGIN_Y)
        self.rows.set_margin_bottom(config.LIST_MARGIN_Y)

        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_overlay_scrolling(True)
        self.add(self.rows)

    # -- filling it ------------------------------------------------------

    def reload(self, mark=None, index=None):
        '''Rebuild every row. Returns False when there is no note at all.

        The cursor goes on `mark` if that note is still there, otherwise on
        row `index` -- which is how deleting leaves it sitting on the note
        that moved up into the gap, so a second Delete carries on from there.

        Rebuilding rather than patching: with a handful of notes it costs
        nothing, and it leaves no room for the question whether what is on
        screen still matches what is on disk.
        '''
        t0 = time.monotonic()
        for child in self.rows.get_children():
            self.rows.remove(child)

        cursor = None
        count = 0
        # Not `index` -- that is the parameter, and shadowing it here left the
        # cursor on the last row every time.
        for position, note in enumerate(notes.overview()):
            row = self._make_row(position, note)
            self.rows.add(row)
            if note.path == mark:
                cursor = row
            count += 1

        self.rows.show_all()

        if cursor is None and index is not None and count:
            cursor = self.rows.get_row_at_index(min(index, count - 1))
        if cursor is None:
            cursor = self.rows.get_row_at_index(0)
        if cursor is not None:
            self.rows.select_row(cursor)

        self._log(f'{count} notes in {(time.monotonic() - t0) * 1000:.1f} ms')
        return count > 0

    def _make_row(self, index, note):
        row = Gtk.ListBoxRow()
        row.path = note.path  # the row knows which note it is
        row.get_style_context().add_class('note')

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=config.ROW_SPACING)

        numbered = index < config.NUMBERED_ROWS
        tile = Gtk.Label(label=str(index + 1) if numbered else '·')
        tile.set_size_request(config.TILE_SIZE, config.TILE_SIZE)
        tile.get_style_context().add_class('tile')

        title = Gtk.Label(label=note.title or config.EMPTY_TITLE)
        title.set_xalign(0)
        title.set_single_line_mode(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        # Without this the label asks for the full width of its text, and a
        # long first line would push the date off the row instead of being
        # cut short.
        title.set_max_width_chars(1)
        title.get_style_context().add_class('note-title')

        when = Gtk.Label(label=notes.short_date(note.changed))
        when.get_style_context().add_class('note-date')

        line.pack_start(tile, False, False, 0)
        line.pack_start(title, True, True, 0)
        line.pack_end(when, False, False, 0)
        row.add(line)

        if not numbered:
            # No digit to press any more. The friction is the reminder to
            # tidy up; these are reached with the arrow keys.
            row.get_style_context().add_class('overflow')
        return row

    # -- input -----------------------------------------------------------

    def handle_key(self, event):
        '''Digits, the new-note key, Delete. Arrows and Enter are the
        ListBox's own.
        '''
        if event.keyval in DIGITS:
            self._choose_index(DIGITS[event.keyval])
            return True

        if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            self._delete_cursor_row()
            return True

        if event.hardware_keycode == NEW_NOTE_KEYCODE \
                or event.keyval in NEW_NOTE_KEYVALS:
            if self.on_new is not None:
                self.on_new()
            return True

        return False

    def _choose_index(self, index):
        row = self.rows.get_row_at_index(index)
        if row is not None:
            self._choose(row)
        # No row there: swallow the key anyway. There is nothing else a digit
        # could mean here, and a stray beep is worse than nothing happening.

    def _delete_cursor_row(self):
        '''Throw away the note under the cursor. Only here, never in the
        editor, where Delete still removes characters.
        '''
        row = self.rows.get_selected_row()
        if row is not None and self.on_delete is not None:
            self.on_delete(row.path, row.get_index())

    def _on_row_activated(self, _listbox, row):
        self._choose(row)

    def _choose(self, row):
        self.rows.select_row(row)
        if self.on_choose is not None:
            self.on_choose(row.path)

    def focus_cursor(self):
        '''Put keyboard focus on the marked row, which also scrolls to it.'''
        row = self.rows.get_selected_row()
        if row is not None:
            row.grab_focus()
        else:
            self.rows.grab_focus()

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} list: {message}",
                  flush=True)
