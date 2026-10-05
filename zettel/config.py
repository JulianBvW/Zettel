'''Constants and paths, all in one place.

Everything here is a default. The installer writes the few that depend on the
machine into `~/.config/zettel/config.json`, which is read at the bottom of
this file. A file is not a settings dialog, so the non-goal stands.
'''

import json
from pathlib import Path

# D-Bus name. Also what `gapplication action <APP_ID> toggle` addresses.
APP_ID = 'io.github.julianbvw.Zettel'

# WM_CLASS. BlurCinnamon matches the window by this, so it has to be set
# before the first window is created and must never change afterwards.
PRG_NAME = 'zettel'       # instance name  -> WM_CLASS field 1
PROGRAM_CLASS = 'Zettel'  # class name     -> WM_CLASS field 2

# Where the window starts out. Only a starting value: size and position are
# free to change and are remembered from then on.
WIDTH = 512
HEIGHT = 660
MARGIN = 24  # distance to the edges of the work area

# Which corner the window starts in. Only ever decides the very first
# appearance and the fallback when a remembered place no longer fits -- after
# that it stays where it was put.
CORNER = 'bottom-right'
CORNERS = ('bottom-right', 'bottom-left', 'top-right', 'top-left')

# Below this the window is no use to anyone, so the resize stops there.
MIN_WIDTH = 320
MIN_HEIGHT = 240

# The invisible band along each edge that starts a resize. Six rather than the
# eight the Design-Ref suggests: the scrollbar slider sits 6 px in from the
# right, and an 8 px band would cover its outer half -- dragging the scrollbar
# would then resize the window. The corners are bigger so they stay hittable.
GRIP_WIDTH = 6
GRIP_CORNER = 16

# How long the window has to sit still before its size and place are written.
STATE_SAVE_DELAY_MS = 400

# The pane itself: dark anthracite, a hairline edge, softly rounded corners.
BG_RGBA = (24 / 255, 28 / 255, 34 / 255, 0.72)
BORDER_RGBA = (1.0, 1.0, 1.0, 0.10)
CORNER_RADIUS = 16

# Without a blurred backdrop, 72 % over a busy wallpaper is hard to read.
# Not used yet -- the installer in phase 6 picks between the two.
BG_RGBA_NO_BLUR = (24 / 255, 28 / 255, 34 / 255, 0.88)

# How long the typing has to pause before the note is written out.
AUTOSAVE_DELAY_MS = 500

# Breathing room around the text. Not decoration -- text running into the
# window edge is hard to read.
EDITOR_MARGIN_X = 24
EDITOR_MARGIN_Y = 22

# As a factor of the font's own line height, so it follows the system font
# size. 1.0 is what the font asks for; the Design-Ref wanted 1.6, which cost
# a quarter of the visible lines -- too much for reading a stack trace.
EDITOR_LINE_HEIGHT = 1.3

# The list. Slightly less room on the right because the scrollbar floats
# there.
LIST_MARGIN_LEFT = 18
LIST_MARGIN_RIGHT = 14
LIST_MARGIN_Y = 20
ROW_SPACING = 13  # between tile, title and date
TILE_SIZE = 24

# Nine notes get a digit. Beyond that the tile goes empty and dashed: the
# friction is the reminder to tidy up, and those rows are still reachable
# with the arrow keys.
NUMBERED_ROWS = 9

# A note that is nothing but blank lines has no first line to show.
EMPTY_TITLE = '\u2014'

# The bare minimum to stay legible on our own dark background. Without this
# the system theme (Mint-Y-Blue, a light one) paints dark text and a nearly
# white scrollbar on it -- measured at rgba(0.99, 0.99, 0.99, 0.98). The full
# styling arrives in phase 4; this is repair, not decoration.
CSS = b'''
textview, textview text {
    background-color: transparent;
    color: #e2e6ea;
    caret-color: #5294e2;
}

/* No trough, no frame, nothing but a floating pill. The scrollbar overlays
   the right padding rather than taking space, so the text never reflows when
   it appears -- and the margin keeps it off the window edge, so it sits in
   that padding instead of clinging to the rim. */
scrollbar,
scrollbar contents,
scrollbar trough,
scrollbar.overlay-indicator,
scrollbar.overlay-indicator trough {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
}

scrollbar slider {
    background-color: rgba(255, 255, 255, 0.18);
    background-image: none;
    border: none;
    border-radius: 5px;
    min-width: 4px;
    min-height: 32px;
    margin: 3px 6px;
}

scrollbar slider:hover {
    background-color: rgba(255, 255, 255, 0.34);
}

/* Dragging is where the theme used to flash white. */
scrollbar slider:active,
scrollbar slider:hover:active {
    background-color: rgba(255, 255, 255, 0.45);
}

scrollbar.overlay-indicator:not(.dragging):not(.hovering) slider {
    background-color: rgba(255, 255, 255, 0.18);
    min-width: 4px;
}

/* -- the list ----------------------------------------------------------
   Same job as the scrollbar rules above: the system theme paints list rows
   on a light background, which is unreadable on our dark glass. Strictly
   this is phase 4 work, pulled forward because an unstyled list is not
   something you can look at long enough to test the rest. */
list.note-list,
list.note-list row {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
}

list.note-list row.note {
    padding: 7px 8px;
    margin-bottom: 4px;
    border-radius: 9px;
    outline: none;
}

/* One mark, not two: this is both the keyboard cursor and "the note you
   are about to open". */
list.note-list row.note:selected {
    background-color: rgba(255, 255, 255, 0.07);
}

.tile {
    background-color: rgba(255, 255, 255, 0.08);
    background-image: none;
    border-radius: 7px;
    color: #aeb5bd;
    font-family: monospace;
    font-size: 12px;
}

/* One of exactly two places the accent colour appears; the other is the
   text cursor. */
list.note-list row.note:selected .tile {
    background-color: #5294e2;
    color: #0f1216;
}

/* The colours below all sit on the label nodes rather than on the row. The
   system theme styles `label` directly, and a colour inherited from the row
   never gets a say against a rule that matches the label itself -- which is
   what painted the titles in the theme's blue. */

list.note-list row.note.overflow .tile {
    background-color: transparent;
    border: 1px dashed rgba(255, 255, 255, 0.14);
    color: #7d858e;
}

list.note-list row.note.overflow:selected .tile {
    background-color: #5294e2;
    border-color: #5294e2;
    color: #0f1216;
}

.note-title {
    font-size: 13px;
    color: #dee2e7;
}

list.note-list row.note:selected .note-title {
    color: #ffffff;
}

.note-date {
    font-size: 11px;
    color: #8b939c;
}

list.note-list row.note:selected .note-date {
    color: #a7aeb6;
}

/* A step paler beyond nine, so the eye sorts them out by itself. */
list.note-list row.note.overflow .note-title {
    color: #b5bcc4;
}

list.note-list row.note.overflow .note-date {
    color: #7d858e;
}

list.note-list row.note.overflow:selected .note-title {
    color: #ffffff;
}

list.note-list row.note.overflow:selected .note-date {
    color: #a7aeb6;
}
'''

# A plain, themed icon so it follows the panel's colour. Not a brand mark:
# the panel is read by shape, not by name.
PANEL_ICON = 'accessories-text-editor-symbolic'

# Where the notes live. The installer asks, and the answer lands in
# config.json -- the folder name is the one thing in the whole program that is
# in the user's language.
NOTES_DIR = Path.home() / 'Notizen'
STATE_FILE = Path.home() / '.config' / 'zettel' / 'state.json'
CONFIG_FILE = Path.home() / '.config' / 'zettel' / 'config.json'


def _apply_user_config():
    '''Let config.json override the few defaults that depend on the machine.

    As suspicious as state.load(), and for a stronger reason: a program that
    will not start because of its settings file is worse than one running with
    the wrong settings. Anything missing, unreadable, malformed or of the
    wrong type simply leaves the default standing.
    '''
    global NOTES_DIR, WIDTH, HEIGHT, CORNER, BG_RGBA

    try:
        settings = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    if not isinstance(settings, dict):
        return

    folder = settings.get('notes_dir')
    if isinstance(folder, str) and folder.strip():
        NOTES_DIR = Path(folder).expanduser()

    for key, name in (('width', 'WIDTH'), ('height', 'HEIGHT')):
        value = settings.get(key)
        # bool is an int to Python, and not one we want here.
        if isinstance(value, int) and not isinstance(value, bool):
            globals()[name] = value

    corner = settings.get('corner')
    if corner in CORNERS:
        CORNER = corner

    # Without a blurred backdrop the window has to carry more of the contrast
    # itself, or text over a busy wallpaper is hard to read.
    blur = settings.get('blur')
    if isinstance(blur, bool):
        BG_RGBA = BG_RGBA if blur else BG_RGBA_NO_BLUR

    WIDTH = max(MIN_WIDTH, WIDTH)
    HEIGHT = max(MIN_HEIGHT, HEIGHT)


_apply_user_config()
