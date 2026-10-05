'''The icon in the panel. A way in when the shortcut is not there.

A tool reachable only through one key is lost the moment that key stops
firing -- which happened twice on 18.09. with other shortcuts. This is the
back door, and the only part of Zettel that is allowed to be absent.
'''

import time

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import config, notes  # noqa: E402

# Mint's own status area. Kept optional: without it -- on any desktop that is
# not Cinnamon -- the program carries on, just without an icon. A missing
# panel icon must not mean a missing scratchpad.
try:
    gi.require_version('XApp', '1.0')
    from gi.repository import XApp
except (ValueError, ImportError):  # pragma: no cover
    XApp = None


class PanelIcon:
    '''Left click toggles the window, right click opens a very short menu.'''

    def __init__(self, app, verbose=False):
        self._app = app
        self._verbose = verbose
        self.icon = None

        if XApp is None:
            self._log('XApp is not available -- no panel icon')
            return

        try:
            self.icon = XApp.StatusIcon()
        except Exception as error:  # pragma: no cover
            self._log(f'could not create the status icon: {error}')
            return

        self.icon.set_name(config.PRG_NAME)
        self.icon.set_icon_name(config.PANEL_ICON)
        self.icon.set_tooltip_text('Zettel')
        self.icon.set_secondary_menu(self._build_menu())
        self.icon.connect('activate', self._on_activate)
        self.icon.set_visible(True)
        self._log('panel icon is up')

    def _build_menu(self):
        menu = Gtk.Menu()

        folder = Gtk.MenuItem.new_with_label('Open notes folder')
        folder.connect('activate', self._on_open_folder)
        menu.append(folder)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem.new_with_label('Quit')
        quit_item.connect('activate', lambda *_: self._app.quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_activate(self, _icon, button, _time):
        # The signal carries the button, so the right one can be left to the
        # menu the panel pops up by itself.
        if button == Gdk.BUTTON_PRIMARY:
            self._app.window.toggle()

    def _on_open_folder(self, _item):
        # It may not exist yet -- nothing is written until a note is kept.
        notes.ensure_dir()
        try:
            Gtk.show_uri_on_window(None, config.NOTES_DIR.as_uri(),
                                   Gdk.CURRENT_TIME)
        except Exception as error:
            self._log(f'could not open the notes folder: {error}')

    def _log(self, message):
        if self._verbose:
            print(f"[zettel] {time.strftime('%H:%M:%S')} panel: {message}",
                  flush=True)
