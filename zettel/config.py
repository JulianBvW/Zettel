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

# Used from phase 2 / phase 5 on. Defined here so the paths live in one place.
NOTES_DIR = Path.home() / 'Notizen'
STATE_FILE = Path.home() / '.config' / 'zettel' / 'state.json'
