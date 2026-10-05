'''The editor: one text view, one note, one autosave timer.'''

import time

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkSource', '4')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, GLib, Gtk, GtkSource, Pango  # noqa: E402

from . import config, notes  # noqa: E402


class EditorView(Gtk.ScrolledWindow):
    '''A scrolling text area that quietly keeps one note on disk.

    There is no save command, because there is nothing to decide. Typing
    stops for half a second and the note is written; leaving it empty and
    closing throws it away. The only state worth naming is `_path`, and it
    stays None until a note has earned a file.
    '''

    def __init__(self, verbose=False):
        super().__init__()
        self._verbose = verbose
        self._path = None          # Path | None -- None while unsaved
        self._save_source = None   # GLib source id of a pending autosave

        # One buffer per note, kept for as long as the program runs. The undo
        # history lives in the buffer, so throwing it away on every close
        # would mean Ctrl+Z forgets everything the moment you press F4.
        self._buffers = {}         # Path -> GtkSource.Buffer
        self._loaded_mtime = {}    # Path -> float, the mtime we read

        self.view = GtkSource.View()
        self.view.set_monospace(True)  # follows the system monospace font
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(config.EDITOR_MARGIN_X)
        self.view.set_right_margin(config.EDITOR_MARGIN_X)
        self.view.set_top_margin(config.EDITOR_MARGIN_Y)
        self.view.set_bottom_margin(config.EDITOR_MARGIN_Y)
        self.view.set_pixels_below_lines(self._extra_line_spacing())

        # Overlay scrolling on purpose: the scrollbar floats above the right
        # padding instead of taking layout space, so the text never shifts
        # when it appears or goes away.
        self.view.connect('button-press-event', self._on_button_press)

        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_overlay_scrolling(True)
        self.add(self.view)

        self.view.set_buffer(self._make_buffer(''))

    def _extra_line_spacing(self):
        '''How much room to add under each line, in pixels.

        GTK 3 CSS has no line-height, so the view has to be told in pixels.
        Computed from the font's own metrics rather than written down, so the
        spacing follows along if the system font size changes.
        '''
        metrics = self.view.get_pango_context().get_metrics(None, None)
        natural = (metrics.get_ascent() + metrics.get_descent()) // Pango.SCALE
        return max(0, round(natural * (config.EDITOR_LINE_HEIGHT - 1)))

    # -- the note in the window ------------------------------------------

    @property
    def path(self):
        '''The note being edited, or None while it has no file.

        The window reads this after commit(): a note thrown away leaves None
        behind, and the list then has nothing to put its cursor on.
        '''
        return self._path

    @property
    def text(self):
        buffer = self.view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(),
                               buffer.get_end_iter(), False)

    def _make_buffer(self, text):
        '''A buffer holding `text`, with a clean undo history.'''
        buffer = GtkSource.Buffer()
        buffer.set_max_undo_levels(-1)  # see refs: the memory cost is bytes

        # Loading must not count as an edit, or Ctrl+Z straight after opening
        # a note would wipe it.
        buffer.begin_not_undoable_action()
        buffer.set_text(text)
        buffer.end_not_undoable_action()

        # set_text() counts as a change, so clear the flag again. From here
        # on it answers exactly one question: has anything happened since we
        # last agreed with the file on disk?
        buffer.set_modified(False)

        buffer.place_cursor(buffer.get_end_iter())
        buffer.connect('changed', self._on_changed)
        return buffer

    def _buffer_for(self, path):
        '''The buffer for `path`, reused if we already have it.

        Reusing it keeps the undo history and the cursor across a close and
        reopen. It is dropped when the file on disk is newer than what we
        read, because then someone changed it behind our back and our history
        would describe a text that no longer exists.
        '''
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = None

        cached = self._buffers.get(path)
        if cached is not None and mtime is not None \
                and mtime == self._loaded_mtime.get(path):
            self._log(f'reusing buffer for {path.name}')
            return cached

        buffer = self._make_buffer(notes.load(path))
        self._buffers[path] = buffer
        self._loaded_mtime[path] = mtime
        return buffer

    def open_note(self, path):
        '''A particular note, by path.'''
        self._cancel_autosave()
        self._path = path
        self.view.set_buffer(self._buffer_for(path))
        self._log(f'opened {path.name}')

    def open_new(self):
        self._cancel_autosave()
        self._path = None
        self.view.set_buffer(self._make_buffer(''))
        self._log('opened a new note')

    # -- the note on disk ------------------------------------------------

    def commit(self, discard=False):
        '''Apply the save rule and stop any pending autosave.

        Anything but whitespace counts as content. Emptying a note and
        leaving therefore deletes it -- which is the only way to delete one,
        and needs no button.
        '''
        self._cancel_autosave()
        text = self.text

        if discard or not text.strip():
            self._forget(self._path)
            self._path = None
            return

        # Only write if something actually changed. Otherwise merely looking
        # at a note would give it a new modification time and send it to the
        # top of the list -- reading is not editing.
        if self.view.get_buffer().get_modified():
            self._write(text)

    def _write(self, text):
        '''Put the text on disk and remember that this is what we have.'''
        if self._path is None:
            self._path = notes.new_path()
        notes.save(self._path, text)
        self.view.get_buffer().set_modified(False)

        # Keep the buffer under its path, and record the mtime we just
        # caused -- otherwise the next open would see a newer file than it
        # loaded and throw the undo history away for nothing.
        self._buffers[self._path] = self.view.get_buffer()
        try:
            self._loaded_mtime[self._path] = self._path.stat().st_mtime
        except OSError:
            self._loaded_mtime.pop(self._path, None)
        self._log(f'saved {self._path.name}')

    def forget_buffer(self, path):
        '''Drop the cached buffer for a note, leaving the file alone.

        For a note deleted from the list: without this its buffer, and the
        undo history inside it, would sit in memory describing a note that is
        no longer there.
        '''
        self._buffers.pop(path, None)
        self._loaded_mtime.pop(path, None)
        if self._path == path:
            self._path = None

    def _forget(self, path):
        if path is None:
            return
        notes.discard(path)
        self._buffers.pop(path, None)
        self._loaded_mtime.pop(path, None)
        self._log(f'discarded {path.name}')

    def _on_button_press(self, view, event):
        '''Right click copies a selection, or pastes when there is none.

        The same gesture Ghostty uses, and it replaces GTK's context menu
        outright -- returning True keeps the menu from ever appearing. Cut,
        copy, paste and select-all stay on the keyboard.
        '''
        if event.button != Gdk.BUTTON_SECONDARY:
            return False

        buffer = view.get_buffer()
        clipboard = view.get_clipboard(Gdk.SELECTION_CLIPBOARD)

        if buffer.get_has_selection():
            # Not placing the cursor here: that would drop the very selection
            # about to be copied.
            buffer.copy_clipboard(clipboard)
        else:
            # Unlike a terminal this has a cursor, so put it where the click
            # was. Text appearing somewhere other than where you pointed
            # would be a surprise.
            bx, by = view.window_to_buffer_coords(
                Gtk.TextWindowType.TEXT, int(event.x), int(event.y))
            found, position = view.get_iter_at_location(bx, by)
            if found:
                buffer.place_cursor(position)
            buffer.paste_clipboard(clipboard, None, True)

        return True

    def _on_changed(self, _buffer):
        self._cancel_autosave()
        self._save_source = GLib.timeout_add(config.AUTOSAVE_DELAY_MS,
                                             self._autosave)

    def _autosave(self):
        '''Write, but never delete.

        Deleting is left to commit(). Clearing the field to retype something
        should not cost you the note, and if the session dies mid-edit the
        old content is the safer thing to be left holding.
        '''
        self._save_source = None
        text = self.text
        if text.strip():
            self._write(text)
        return GLib.SOURCE_REMOVE

    def _cancel_autosave(self):
        if self._save_source is not None:
            GLib.source_remove(self._save_source)
            self._save_source = None

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} editor: {message}",
                  flush=True)
