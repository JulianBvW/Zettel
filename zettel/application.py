'''The application object: one instance, reachable over the session bus.'''

import signal
import time

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import config  # noqa: E402
from .panelicon import PanelIcon  # noqa: E402
from .window import ZettelWindow  # noqa: E402


class ZettelApplication(Gtk.Application):
    '''Runs from login to logout and does nothing most of the time.

    Actions registered here are exported on the session bus automatically,
    which is what lets the keyboard shortcuts reach us without starting a
    second Python interpreter:

        gapplication action io.github.julianbvw.Zettel toggle
        gapplication action io.github.julianbvw.Zettel scratch
    '''

    def __init__(self, verbose=False):
        super().__init__(
            application_id=config.APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._verbose = verbose
        self.window = None
        self.panel_icon = None

    # -- lifecycle -------------------------------------------------------

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Keep running with no window on screen. Without this the application
        # would be free to quit the moment we hide, and the next key press
        # would pay for a cold start.
        self.hold()

        self.window = ZettelWindow(verbose=self._verbose)
        self.add_window(self.window)

        # The way in when the shortcut is not there. Kept after the window,
        # because clicking it needs a window to toggle.
        self.panel_icon = PanelIcon(self, verbose=self._verbose)

        for name, handler in (
            ('toggle', lambda *_: self.window.toggle()),
            ('scratch', lambda *_: self.window.scratch()),
            ('show', lambda *_: self.window.show_zettel()),
            ('hide', lambda *_: self.window.close_zettel()),
            ('quit', lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', self._timed(name, handler))
            self.add_action(action)

        # Logging out sends SIGTERM, and Python would die on the spot without
        # ever reaching do_shutdown. Routed through the main loop instead, so
        # whatever is on screen still gets written out.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             self._on_sigterm)

        self._log('ready')

    def do_shutdown(self):
        # The last chance to keep what was typed. Through the window, so the
        # same rule applies as on closing: nothing to do unless a note is
        # actually open in the editor.
        if self.window is not None:
            self.window.commit()
            self._log('committed on shutdown')
        Gtk.Application.do_shutdown(self)

    def _on_sigterm(self):
        self._log('SIGTERM')
        self.quit()  # runs do_shutdown, which saves
        return GLib.SOURCE_REMOVE

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if '--daemon' in args:
            # Started from autostart: be there, but stay out of the way.
            self._log('started in daemon mode')
        else:
            self.window.toggle()
        return 0

    def do_activate(self):
        # Reached when something activates us without a command line.
        self.window.toggle()

    # -- misc ------------------------------------------------------------

    def _timed(self, name, handler):
        '''Wrap an action so --verbose can show how long it took.'''
        def wrapper(*args):
            t0 = time.monotonic()
            handler(*args)
            # Double quotes here: the message itself contains apostrophes.
            self._log(f"action '{name}' handled in "
                      f'{(time.monotonic() - t0) * 1000:.1f} ms')
        return wrapper

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} app: {message}",
                  flush=True)
