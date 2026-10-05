'''The window itself: transparent, undecorated, parked in the bottom right.'''

import math
import time

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import config, grips, state  # noqa: E402
from .editor import EditorView  # noqa: E402
from .notelist import ListView  # noqa: E402

# X11-only, and only needed for a fresh server timestamp. Kept optional so the
# import does not bring the whole program down on a session without it.
try:
    gi.require_version('GdkX11', '3.0')
    from gi.repository import GdkX11
except (ValueError, ImportError):  # pragma: no cover
    GdkX11 = None


class ZettelWindow(Gtk.Window):
    '''A window that spends most of its life hidden.

    It is never destroyed and never rebuilt. Showing it is only a matter of
    mapping it again, which is the whole reason the program stays resident:
    there is no startup left to pay for at the moment the key is pressed.
    '''

    def __init__(self, verbose=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._verbose = verbose

        self._state = state.load()
        self._save_source = None   # GLib source id of a pending state write
        self._saved = None         # the geometry already on disk
        if self._state['x'] is not None:
            # Already on disk, so starting up need not write it again.
            self._saved = (self._state['x'], self._state['y'],
                           self._state['width'], self._state['height'])

        self.set_title('Zettel')
        self.set_decorated(False)

        # NORMAL, not UTILITY. BlurCinnamon only accepts NORMAL, DOCK and
        # DESKTOP (extension.js:2965) -- with UTILITY the window would simply
        # never be blurred, and without any error to go on.
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        # It is an overlay, not a window you manage.
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)

        # We place the window ourselves; do not let GTK centre it.
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_default_size(self._state['width'], self._state['height'])

        # A floor for the resize, stated as a window manager hint rather than
        # a widget size request, so it constrains the drag rather than the
        # layout inside.
        floor = Gdk.Geometry()
        floor.min_width = config.MIN_WIDTH
        floor.min_height = config.MIN_HEIGHT
        self.set_geometry_hints(None, floor, Gdk.WindowHints.MIN_SIZE)

        self._install_css()
        self._rgba = self._setup_transparency()
        self.connect('draw', self._on_draw)
        self.connect('key-press-event', self._on_key_press)
        self.connect('configure-event', self._on_configure)

        # Closing the window would destroy it and cost us the instant reopen.
        # Hide instead -- the only way out is the quit action.
        self.connect('delete-event', lambda *_: self.close_zettel() or True)

        self.editor = EditorView(verbose=verbose)
        self.list = ListView(verbose=verbose)
        self.list.on_choose = self.open_note
        self.list.on_new = self.new_note

        # Two contents, one window. The stack swaps them without a new window,
        # without a rebuild and without a change in size -- so switching views
        # costs exactly one redraw and nothing moves.
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self._stack.add_named(self.list, 'list')
        self._stack.add_named(self.editor, 'editor')

        # The grab zones for resizing have to lie over the contents, because
        # the text view handles button presses itself and would swallow them.
        self._overlay = Gtk.Overlay()
        self._overlay.add(self._stack)
        grips.install(self, self._overlay)
        self.add(self._overlay)

        # The stack refuses to switch to a child that is not visible itself,
        # and a widget being visible does not put it on screen -- that only
        # happens once the window is mapped. So show the contents now and let
        # the window decide when anything is seen.
        self._overlay.show_all()

        # Realise early so there is a GdkWindow to ask for a server timestamp
        # the first time we are shown.
        self.realize()

    # -- appearance ------------------------------------------------------

    def _install_css(self):
        '''Style sheet for the whole process, not just one widget.

        Per-widget providers do not reach child widgets, and the scrollbar is
        a sibling of the text view rather than part of it -- which is exactly
        why it kept the light system theme and flashed white while dragging.
        '''
        provider = Gtk.CssProvider()
        provider.load_from_data(config.CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _setup_transparency(self):
        '''Ask for an RGBA visual. Returns True if we actually got one.'''
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)
            return True
        # No compositing: paint opaque rather than leave a black rectangle.
        self._log('no RGBA visual or no compositor -- falling back to opaque')
        return False

    def _on_draw(self, _widget, cr):
        r, g, b, a = config.BG_RGBA

        if not self._rgba:
            # No alpha channel to work with. Rounded corners would be four
            # black wedges, so stay square and opaque.
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgb(r, g, b)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            return False

        # Wipe the whole surface to nothing first. Filling only the rounded
        # path would leave whatever was outside it standing -- the corners
        # have to be made transparent on purpose.
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        width = self.get_allocated_width()
        height = self.get_allocated_height()
        radius = config.CORNER_RADIUS

        # The pane, filled right out to the edge.
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.set_source_rgba(r, g, b, a)
        cr.fill()

        # The hairline, on a path of its own half a pixel further in. A one
        # pixel line is drawn centred on its path, so only there does it land
        # on one whole row of pixels instead of smearing across two. Filling
        # and stroking the same path would leave the outermost row half
        # covered, and the edge would read as washed out rather than drawn.
        self._rounded_rect(cr, 0.5, 0.5, width - 1, height - 1, radius - 0.5)
        cr.set_source_rgba(*config.BORDER_RGBA)
        cr.set_line_width(1)
        cr.stroke()
        return False

    @staticmethod
    def _rounded_rect(cr, x, y, width, height, radius):
        '''A rectangle with rounded corners as the current path.'''
        radius = min(radius, width / 2, height / 2)
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()

    # -- showing and hiding ----------------------------------------------

    def toggle(self):
        '''F4: open the list, or apply the save rule and close.'''
        if self.get_visible():
            self.close_zettel()
        else:
            self.show_zettel()

    def scratch(self):
        '''Shift+F4: a fresh note, or throw this one away.

        Closed, it hands you a blank surface; open, it discards. Together
        that is the whole clipboard round trip -- open, paste, tidy up, copy
        out, throw away -- without a file ever existing.
        '''
        if self.get_visible():
            self.close_zettel(discard=True)
        else:
            self.show_zettel(new=True)

    def show_zettel(self, new=False):
        t0 = time.monotonic()

        # Fill before mapping, so the content is on screen the moment the
        # window is. Reading a few kilobytes costs nothing next to that.
        if new:
            self.new_note()
        else:
            self.show_list()

        # Reposition on every show: X11 window managers are free to place a
        # window when it is mapped, and some do.
        self.move(*self._placement())
        self.show_all()

        # A window shown from a D-Bus call has no user event behind it, so the
        # window manager may refuse it the keyboard to prevent focus stealing.
        # A fresh server timestamp is what makes the request legitimate.
        ts = self._server_time()
        self.present_with_time(ts)

        gdk_window = self.get_window()
        if gdk_window is not None:
            gdk_window.focus(ts)
        self._focus_view()

        self._log(f'shown in {(time.monotonic() - t0) * 1000:.1f} ms '
                  f'at {self.get_position()}')

    def close_zettel(self, discard=False):
        # Write or delete first, then disappear -- so what is on screen and
        # what is on disk never disagree, not even for a frame.
        self.commit(discard=discard)
        # A resize in the last fraction of a second still has its write
        # pending. Do it now, while there is still a window to ask.
        if self._save_source is not None:
            self._cancel_state_save()
            self._save_state()
        self.hide()
        self._log('hidden, discarded' if discard else 'hidden')

    def commit(self, discard=False):
        '''The save rule, but only when a note is actually being edited.

        Coming from the list there is nothing to write: Alt+Left already
        committed on the way out of the editor.
        '''
        if self._editing:
            self.editor.commit(discard=discard)

    # -- the two views ---------------------------------------------------

    @property
    def _editing(self):
        return self._stack.get_visible_child_name() == 'editor'

    def show_list(self, mark=None):
        '''Show the list, cursor on `mark`.

        With no notes at all the list would be an empty rectangle and a dead
        end for anyone who does not know the ` key by heart, so that case
        goes straight into a new note instead.
        '''
        if not self.list.reload(mark):
            self.new_note()
            return
        self._stack.set_visible_child_name('list')
        self._focus_view()

    def new_note(self):
        self.editor.open_new()
        self._stack.set_visible_child_name('editor')
        self._focus_view()

    def open_note(self, path):
        self.editor.open_note(path)
        self._stack.set_visible_child_name('editor')
        self._focus_view()

    def back_to_list(self, discard=False):
        '''Alt+Left: the same save rule as F4, but back instead of away.'''
        self.editor.commit(discard=discard)
        # After commit the path is None if the note was thrown away -- then
        # there is nothing left for the cursor to sit on.
        self.show_list(mark=self.editor.path)

    def _focus_view(self):
        if self._editing:
            self.editor.view.grab_focus()
        else:
            self.list.focus_cursor()

    # -- size and place --------------------------------------------------

    def _placement(self):
        '''Where you last left it, or the default corner.'''
        x, y = self._state['x'], self._state['y']
        if x is not None and self._fits(x, y):
            return x, y
        return self._target_position()

    def _fits(self, x, y):
        '''Does the whole window land inside a work area?

        A remembered place is checked rather than believed: unplug the second
        monitor, change the resolution or move the panel, and the coordinates
        in state.json point somewhere that no longer exists.
        '''
        width, height = self.get_size()
        monitor = Gdk.Display.get_default().get_monitor_at_point(
            x + width // 2, y + height // 2)
        if monitor is None:
            return False
        area = monitor.get_workarea()
        return (x >= area.x and y >= area.y
                and x + width <= area.x + area.width
                and y + height <= area.y + area.height)

    def _on_configure(self, _widget, _event):
        '''Moved or resized. Write it down, but not on every single step.

        A drag produces a stream of these; debouncing turns the whole gesture
        into one write instead of dozens.
        '''
        if self.get_visible():
            self._cancel_state_save()
            self._save_source = GLib.timeout_add(
                config.STATE_SAVE_DELAY_MS, self._save_state)
        return False

    def _save_state(self):
        self._save_source = None
        if not self.get_visible():
            # A hidden window has no honest position to report.
            return GLib.SOURCE_REMOVE

        geometry = (*self.get_position(), *self.get_size())
        if geometry != self._saved:
            state.save(*geometry)
            self._saved = geometry
            (self._state['x'], self._state['y'],
             self._state['width'], self._state['height']) = geometry
            self._log(f'remembered {geometry}')
        return GLib.SOURCE_REMOVE

    def _cancel_state_save(self):
        if self._save_source is not None:
            GLib.source_remove(self._save_source)
            self._save_source = None

    def _target_position(self):
        '''Bottom right of the work area -- that is the screen minus panels.

        Asking for the work area means the panel height is never written down
        anywhere, and the position stays right if the panel ever changes.
        '''
        display = Gdk.Display.get_default()
        gdk_window = self.get_window()
        if gdk_window is not None:
            monitor = display.get_monitor_at_window(gdk_window)
        else:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        wa = monitor.get_workarea()
        width, height = self.get_size()
        x = wa.x + wa.width - width - config.MARGIN
        y = wa.y + wa.height - height - config.MARGIN
        return x, y

    def _server_time(self):
        gdk_window = self.get_window()
        if GdkX11 is not None and gdk_window is not None:
            try:
                return GdkX11.x11_get_server_time(gdk_window)
            except Exception:  # not an X11 window
                pass
        return Gdk.CURRENT_TIME

    # -- input -----------------------------------------------------------

    def _on_key_press(self, _widget, event):
        # This runs before the focused widget sees the key, which is what
        # makes Alt+Left reliable -- the text view would otherwise treat it as
        # a cursor movement. For the same reason the digits are only taken
        # when the list is up: in the editor they are just characters.
        #
        # Esc closes. F4 is deliberately not handled here: the global shortcut
        # is a passive grab on the root window, so that key press never reaches
        # us at all -- both directions run through the same action.
        if event.keyval == Gdk.KEY_Escape:
            self.close_zettel()
            return True

        if self._editing:
            if event.keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left) \
                    and event.state & Gdk.ModifierType.MOD1_MASK:
                discard = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
                self.back_to_list(discard=discard)
                return True
            return False

        return self.list.handle_key(event)

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} window: {message}",
                  flush=True)
