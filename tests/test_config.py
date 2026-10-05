'''What config.json is allowed to change, and what it may not break.

    /usr/bin/python3 tests/test_config.py
'''

import tempfile
from pathlib import Path

from harness import check, report, section

from zettel import config  # noqa: E402

SANDBOX = Path(tempfile.mkdtemp(prefix='zettel-config-'))
config.CONFIG_FILE = SANDBOX / 'config.json'

DEFAULTS = {name: getattr(config, name)
            for name in ('NOTES_DIR', 'WIDTH', 'HEIGHT', 'CORNER', 'BG_RGBA')}


def reset():
    for name, value in DEFAULTS.items():
        setattr(config, name, value)


def apply(text):
    reset()
    if text is None:
        if config.CONFIG_FILE.exists():
            config.CONFIG_FILE.unlink()
    else:
        config.CONFIG_FILE.write_text(text, encoding='utf-8')
    config._apply_user_config()


section('1) No file, no change')
apply(None)
check('everything as configured',
      all(getattr(config, n) == v for n, v in DEFAULTS.items()))

section('2) A complete file is honoured')
apply('{"notes_dir": "~/Zettelkasten", "width": 640, "height": 700,'
      ' "corner": "top-left", "blur": true}')
check('notes folder, with ~ expanded',
      config.NOTES_DIR == Path.home() / 'Zettelkasten', config.NOTES_DIR)
check('width', config.WIDTH == 640)
check('height', config.HEIGHT == 700)
check('corner', config.CORNER == 'top-left')
check('blur keeps the lighter background',
      config.BG_RGBA == DEFAULTS['BG_RGBA'])

section('3) No blur means a denser background')
apply('{"blur": false}')
check('the other value is used',
      config.BG_RGBA == config.BG_RGBA_NO_BLUR, config.BG_RGBA)
check('and it really is denser',
      config.BG_RGBA[3] > DEFAULTS['BG_RGBA'][3])

section('4) Rubbish leaves the defaults standing')
for broken in ('', 'not json', '[1,2,3]', '"a string"', 'null', '{}',
               '{"width": "wide", "height": null, "corner": 7, "blur": "yes",'
               ' "notes_dir": 42}'):
    apply(broken)
    check(f'survives {broken[:28]!r}',
          all(getattr(config, n) == v for n, v in DEFAULTS.items()),
          (config.WIDTH, config.HEIGHT, config.CORNER, str(config.NOTES_DIR)))

section('5) Booleans are not sizes, and an empty folder is no folder')
apply('{"width": true, "notes_dir": "   "}')
check('true is not a width', config.WIDTH == DEFAULTS['WIDTH'])
check('blank is not a path', config.NOTES_DIR == DEFAULTS['NOTES_DIR'])

section('6) A corner we do not know is ignored')
apply('{"corner": "middle"}')
check('default kept', config.CORNER == DEFAULTS['CORNER'])

section('7) Too small is lifted to the floor')
apply('{"width": 10, "height": 10}')
check('width', config.WIDTH == config.MIN_WIDTH)
check('height', config.HEIGHT == config.MIN_HEIGHT)

section('8) Unknown keys are simply not our business')
apply('{"width": 600, "colour": "purple", "nonsense": [1, 2]}')
check('the known one took', config.WIDTH == 600)
check('and nothing blew up', config.CORNER == DEFAULTS['CORNER'])

reset()
report(SANDBOX)
