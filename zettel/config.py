'''Constants and paths, all in one place.'''

from pathlib import Path

# D-Bus name. Also what `gapplication action <APP_ID> toggle` addresses.
APP_ID = 'io.github.julianbvw.Zettel'

# WM_CLASS. BlurCinnamon matches the window by this, so it has to be set
# before the first window is created and must never change afterwards.
PRG_NAME = 'zettel'       # instance name  -> WM_CLASS field 1
PROGRAM_CLASS = 'Zettel'  # class name     -> WM_CLASS field 2

# Window geometry. Becomes a starting value once phase 5 makes it resizable.
WIDTH = 512
HEIGHT = 660
MARGIN = 24  # distance to the edges of the work area

# Provisional background until phase 4 brings the real styling.
BG_RGBA = (24 / 255, 28 / 255, 34 / 255, 0.72)

# How long the typing has to pause before the note is written out.
AUTOSAVE_DELAY_MS = 500

# Breathing room around the text. Not decoration -- text running into the
# window edge is hard to read.
EDITOR_MARGIN_X = 24
EDITOR_MARGIN_Y = 22

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
'''

# Where the notes live. Phase 6 makes the folder name configurable.
NOTES_DIR = Path.home() / 'Notizen'
STATE_FILE = Path.home() / '.config' / 'zettel' / 'state.json'
