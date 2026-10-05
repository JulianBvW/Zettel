'''What the window remembers between sessions: how big it is and where.

Free of GTK, like notes.py, so the rules can be checked without a display.
'''

import json

from . import config

KEYS = ('x', 'y', 'width', 'height')


def defaults():
    '''Where the window starts out before it has been moved or resized.

    `x` and `y` are None on purpose: the right place for a window that has
    never been placed depends on the screen, and that is the window's business
    rather than this file's.
    '''
    return {'x': None, 'y': None,
            'width': config.WIDTH, 'height': config.HEIGHT}


def load():
    '''The remembered geometry, or the defaults for anything doubtful.

    Deliberately suspicious. A missing file, half-written JSON, a string where
    a number belongs, a width of four pixels -- every one of those falls back
    to a sane value rather than raising. Losing the remembered size is a
    nuisance; a scratchpad that will not open because of it is not.
    '''
    state = defaults()
    try:
        stored = json.loads(config.STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return state
    if not isinstance(stored, dict):
        return state

    for key in KEYS:
        value = stored.get(key)
        # bool is an int as far as Python is concerned, and not one we want.
        if isinstance(value, int) and not isinstance(value, bool):
            state[key] = value

    state['width'] = max(config.MIN_WIDTH, state['width'])
    state['height'] = max(config.MIN_HEIGHT, state['height'])

    # A position is a pair. One half of one is no position at all.
    if state['x'] is None or state['y'] is None:
        state['x'] = state['y'] = None

    return state


def save(x, y, width, height):
    '''Write the geometry, or quietly give up.

    Through a neighbouring file and a rename, so that dying mid-write leaves
    the previous version intact instead of half a file that the next start
    would throw away.
    '''
    path = config.STATE_FILE
    scratch = path.with_suffix(path.suffix + '.tmp')
    data = {'x': x, 'y': y, 'width': width, 'height': height}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text(json.dumps(data, indent=2) + '\n',
                           encoding='utf-8')
        scratch.replace(path)
    except OSError:
        # Not being able to remember the window size is not worth a crash.
        pass
