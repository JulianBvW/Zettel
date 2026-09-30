'''The window itself: transparent, undecorated, parked in the bottom right.'''

import time

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import config  # noqa: E402
from .editor import EditorView  # noqa: E402

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
        self.set_default_size(config.WIDTH, config.HEIGHT)

        self._install_css()
        self._rgba = self._setup_transparency()
        self.connect('draw', self._on_draw)
        self.connect('key-press-event', self._on_key_press)

        # Closing the window would destroy it and cost us the instant reopen.
        # Hide instead -- the only way out is the quit action.
        self.connect('delete-event', lambda *_: self.hide_zettel() or True)

        self.editor = EditorView(verbose=verbose)
        self.add(self.editor)

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
        cr.set_operator(cairo.OPERATOR_SOURCE)
        if self._rgba:
            cr.set_source_rgba(r, g, b, a)
        else:
            cr.set_source_rgb(r, g, b)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    # -- showing and hiding ----------------------------------------------

    def toggle(self):
        '''F4: open the most recent note, or apply the save rule and close.'''
        if self.get_visible():
            self.hide_zettel()
        else:
            self.show_zettel()

    def scratch(self):
        '''Shift+F4: a fresh note, or throw this one away.

        Closed, it hands you a blank surface; open, it discards. Together
        that is the whole clipboard round trip -- open, paste, tidy up, copy
        out, throw away -- without a file ever existing.
        '''
        if self.get_visible():
            self.hide_zettel(discard=True)
        else:
            self.show_zettel(new=True)

    def show_zettel(self, new=False):
        t0 = time.monotonic()

        # Load before mapping, so the note is on screen the moment the window
        # is. Reading a few kilobytes costs nothing next to that.
        if new:
            self.editor.open_new()
        else:
            self.editor.open_latest()

        # Reposition on every show: X11 window managers are free to place a
        # window when it is mapped, and some do.
        self.move(*self._target_position())
        self.show_all()

        # A window shown from a D-Bus call has no user event behind it, so the
        # window manager may refuse it the keyboard to prevent focus stealing.
        # A fresh server timestamp is what makes the request legitimate.
        ts = self._server_time()
        self.present_with_time(ts)

        gdk_window = self.get_window()
        if gdk_window is not None:
            gdk_window.focus(ts)
        self.editor.view.grab_focus()

        self._log(f'shown in {(time.monotonic() - t0) * 1000:.1f} ms '
                  f'at {self.get_position()}')

    def hide_zettel(self, discard=False):
        # Write or delete first, then disappear -- so what is on screen and
        # what is on disk never disagree, not even for a frame.
        self.editor.commit(discard=discard)
        self.hide()
        self._log('hidden, discarded' if discard else 'hidden')

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
        # Esc closes. F4 is deliberately not handled here: the global shortcut
        # is a passive grab on the root window, so that key press never reaches
        # us at all -- both directions run through the same action.
        if event.keyval == Gdk.KEY_Escape:
            self.hide_zettel()
            return True
        return False

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} window: {message}",
                  flush=True)
