'''The remembered window geometry. No GTK, no display.

    /usr/bin/python3 tests/test_state.py
'''

import tempfile
from pathlib import Path

from harness import check, report, section

from zettel import config  # noqa: E402

SANDBOX = Path(tempfile.mkdtemp(prefix='zettel-state-'))
config.STATE_FILE = SANDBOX / 'zettel' / 'state.json'

from zettel import state  # noqa: E402


def write_raw(text):
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(text, encoding='utf-8')


def clear():
    if config.STATE_FILE.exists():
        config.STATE_FILE.unlink()


section('1) Nothing remembered yet')
clear()
first = state.load()
check('the configured size', (first['width'], first['height']) ==
      (config.WIDTH, config.HEIGHT), first)
check('no place yet', first['x'] is None and first['y'] is None, first)

section('2) There and back again')
state.save(1200, 400, 640, 700)
again = state.load()
check('all four survive',
      (again['x'], again['y'], again['width'], again['height']) ==
      (1200, 400, 640, 700), again)
check('the folder was created', config.STATE_FILE.parent.is_dir())

section('3) Nonsense is ignored, not raised')
for broken in ('', 'not json at all', '[1, 2, 3]', '"a string"', 'null',
               '{"width": "wide", "height": null, "x": [], "y": {}}'):
    write_raw(broken)
    got = state.load()
    check(f'falls back on {broken[:24]!r}',
          (got['width'], got['height']) == (config.WIDTH, config.HEIGHT) and
          got['x'] is None, got)

section('4) Booleans are not numbers')
write_raw('{"x": true, "y": false, "width": true, "height": 700}')
got = state.load()
check('true is not an x', got['x'] is None, got)
check('the real number came through', got['height'] == 700, got)

section('5) Too small is lifted to the floor')
write_raw('{"x": 10, "y": 10, "width": 4, "height": 1}')
got = state.load()
check('width lifted', got['width'] == config.MIN_WIDTH, got)
check('height lifted', got['height'] == config.MIN_HEIGHT, got)
check('the place is kept', (got['x'], got['y']) == (10, 10), got)

section('6) Half a position is no position')
write_raw('{"x": 500, "height": 700, "width": 500}')
got = state.load()
check('x dropped along with the missing y',
      got['x'] is None and got['y'] is None, got)

section('7) A failed write leaves the old file alone')
clear()
state.save(100, 200, 500, 600)
before = config.STATE_FILE.read_text(encoding='utf-8')
leftover = config.STATE_FILE.with_suffix(config.STATE_FILE.suffix + '.tmp')
leftover.write_text('half a fi', encoding='utf-8')  # as if we died mid-write
after = state.load()
check('the previous version still reads',
      (after['width'], after['height']) == (500, 600), after)
check('the file itself is untouched',
      config.STATE_FILE.read_text(encoding='utf-8') == before)

section('8) An unwritable place is not a crash')
config.STATE_FILE = SANDBOX / 'nope' / 'deeper' / 'state.json'
config.STATE_FILE.parent.parent.mkdir(parents=True, exist_ok=True)
config.STATE_FILE.parent.parent.chmod(0o500)
try:
    state.save(1, 2, 500, 600)
    check('save stayed quiet', True)
    check('load gives the defaults', state.load()['width'] == config.WIDTH)
finally:
    config.STATE_FILE.parent.parent.chmod(0o700)

report(SANDBOX)
