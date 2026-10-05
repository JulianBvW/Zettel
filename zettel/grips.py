'''The invisible band along the window's edges that starts a resize.

An undecorated window has no frame for the window manager to offer, so the
edges have to be caught here and handed back to it.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import config  # noqa: E402

START = Gtk.Align.START
END = Gtk.Align.END
FILL = Gtk.Align.FILL

# Edges first, corners after: an overlay stacks its children in the order they
# are added, so the corners end up on top and win where the two meet.
ZONES = (
    (Gdk.WindowEdge.NORTH, 'n-resize', FILL, START, -1, config.GRIP_WIDTH),
    (Gdk.WindowEdge.SOUTH, 's-resize', FILL, END, -1, config.GRIP_WIDTH),
    (Gdk.WindowEdge.WEST, 'w-resize', START, FILL, config.GRIP_WIDTH, -1),
    (Gdk.WindowEdge.EAST, 'e-resize', END, FILL, config.GRIP_WIDTH, -1),

    (Gdk.WindowEdge.NORTH_WEST, 'nw-resize', START, START,
     config.GRIP_CORNER, config.GRIP_CORNER),
    (Gdk.WindowEdge.NORTH_EAST, 'ne-resize', END, START,
     config.GRIP_CORNER, config.GRIP_CORNER),
    (Gdk.WindowEdge.SOUTH_WEST, 'sw-resize', START, END,
     config.GRIP_CORNER, config.GRIP_CORNER),
    (Gdk.WindowEdge.SOUTH_EAST, 'se-resize', END, END,
     config.GRIP_CORNER, config.GRIP_CORNER),
)

_cursors = {}


def _cursor(name):
    if name not in _cursors:
        _cursors[name] = Gdk.Cursor.new_from_name(Gdk.Display.get_default(),
                                                  name)
    return _cursors[name]


def install(window, overlay):
    '''Put eight grab zones over `overlay`, resizing `window`.

    They have to sit in an overlay rather than being handled on the window
    itself: the text view consumes button presses, so a handler on the window
    would never see one anywhere near the text.
    '''
    for edge, cursor_name, halign, valign, width, height in ZONES:
        zone = Gtk.EventBox()

        # No window of its own to draw into, but still one to receive events
        # through -- which is exactly what an invisible grab zone is.
        zone.set_visible_window(False)
        zone.set_size_request(width, height)
        zone.set_halign(halign)
        zone.set_valign(valign)
        zone.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.ENTER_NOTIFY_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)

        # The extra arguments ride along on connect() rather than being closed
        # over, so the loop variables cannot change underneath the handlers.
        zone.connect('enter-notify-event', _on_enter, cursor_name)
        zone.connect('leave-notify-event', _on_leave)
        zone.connect('button-press-event', _on_press, window, edge)

        overlay.add_overlay(zone)


def _on_enter(zone, _event, cursor_name):
    gdk_window = zone.get_window()
    if gdk_window is not None:
        gdk_window.set_cursor(_cursor(cursor_name))
    return False


def _on_leave(zone, _event):
    gdk_window = zone.get_window()
    if gdk_window is not None:
        gdk_window.set_cursor(None)  # back to whatever the parent says
    return False


def _on_press(_zone, event, window, edge):
    if event.button != Gdk.BUTTON_PRIMARY:
        return False
    # From here the window manager runs the drag, anchor point and all.
    window.begin_resize_drag(edge, event.button,
                             int(event.x_root), int(event.y_root), event.time)
    return True
