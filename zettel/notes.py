'''Reading and writing notes.

Deliberately free of GTK: the storage rules are the part worth reasoning
about on their own, and they should be testable without a display.

A note is a plain UTF-8 text file. There is no index, no database and no
metadata -- the filesystem already knows when a file changed, and the first
line of the text is title enough.
'''

from collections import namedtuple
from datetime import datetime

from . import config

# What the list needs to draw one row. `changed` is an mtime, the same number
# the sorting uses, so nobody has to ask the filesystem twice.
NoteInfo = namedtuple('NoteInfo', 'path title changed')

TITLE_MAX = 200      # characters; the label ellipsizes long before this
TITLE_LINES = 20     # how far to look for a line with something on it


def ensure_dir():
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)


def new_path():
    '''A path for a note that does not exist yet.

    Named after the moment it was started, so the notes also sort
    chronologically in a file manager. Two notes begun within the same second
    get a counter.
    '''
    ensure_dir()
    stem = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    path = config.NOTES_DIR / f'{stem}.txt'
    counter = 2
    while path.exists():
        path = config.NOTES_DIR / f'{stem}-{counter}.txt'
        counter += 1
    return path


def all_notes():
    '''Every note, most recently changed first.'''
    if not config.NOTES_DIR.is_dir():
        return []

    dated = []
    for path in config.NOTES_DIR.glob('*.txt'):
        try:
            dated.append((path.stat().st_mtime, path))
        except OSError:
            # Vanished between listing and asking. Nothing to do about it.
            continue
    dated.sort(reverse=True)
    return [path for _, path in dated]


def latest():
    '''The note to show when no particular one was asked for.'''
    found = all_notes()
    return found[0] if found else None


def load(path):
    # A note edited elsewhere may not be valid UTF-8. Showing it with a
    # replacement character beats refusing to open it.
    return path.read_text(encoding='utf-8', errors='replace')


def save(path, text):
    ensure_dir()
    path.write_text(text, encoding='utf-8')


def title(path):
    '''The first line with something on it. That is the note's name.

    Nothing is ever named by hand, so the text has to name itself. Read with
    a byte bound rather than all at once: a note pasted from a browser can be
    a single line of several megabytes, and we only want its beginning.
    '''
    try:
        with path.open(encoding='utf-8', errors='replace') as handle:
            for _ in range(TITLE_LINES):
                line = handle.readline(TITLE_MAX * 4)
                if not line:
                    break
                line = line.strip()
                if line:
                    return line[:TITLE_MAX]
    except OSError:
        pass
    return ''


def short_date(timestamp):
    '''When a note was last touched, in as few characters as possible.

    Today is a time, this year is a day and a month, anything older carries
    the year as well -- two notes a year apart would otherwise read alike.
    '''
    when = datetime.fromtimestamp(timestamp)
    today = datetime.now()
    if when.date() == today.date():
        return when.strftime('%H:%M')
    if when.year == today.year:
        return when.strftime('%d.%m.')
    return when.strftime('%d.%m.%y')


def overview():
    '''Everything the list shows, most recently changed first.'''
    if not config.NOTES_DIR.is_dir():
        return []

    found = []
    for path in config.NOTES_DIR.glob('*.txt'):
        try:
            changed = path.stat().st_mtime
        except OSError:
            continue  # vanished between listing and asking
        found.append(NoteInfo(path, title(path), changed))

    found.sort(key=lambda note: note.changed, reverse=True)
    return found


def discard(path):
    '''Delete a note. Already gone is fine -- that is the wanted end state.'''
    if path is not None:
        path.unlink(missing_ok=True)
