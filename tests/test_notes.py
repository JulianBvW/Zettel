'''The storage rules on their own -- no GTK, no display needed.

    /usr/bin/python3 tests/test_notes.py
'''

import os
from datetime import datetime
from pathlib import Path

from gi.repository import GLib

from harness import check, report, sandbox, section

NOTES_DIR = sandbox()  # must happen before notes is used

from zettel import notes  # noqa: E402


def write(name, text, when=None):
    path = NOTES_DIR / name
    path.write_text(text, encoding='utf-8')
    if when is not None:
        os.utime(path, (when, when))
    return path


section('1) The title is the first line that has something on it')
check('plain first line',
      notes.title(write('a.txt', 'Shopping\nMilk')) == 'Shopping')
check('leading blank lines are skipped',
      notes.title(write('b.txt', '\n\n   \nReally the title\nmore')) ==
      'Really the title')
check('surrounding whitespace is trimmed',
      notes.title(write('c.txt', '   indented   \n')) == 'indented')
check('a note of nothing but whitespace has no title',
      notes.title(write('d.txt', '  \n\t\n')) == '')
check('a file that is not there has no title',
      notes.title(NOTES_DIR / 'never-existed.txt') == '')

section('2) A pasted wall of text does not become the title verbatim')
long_title = notes.title(write('e.txt', 'x' * 100000))
check('capped', len(long_title) == notes.TITLE_MAX, len(long_title))

section('3) Short dates')
now = datetime.now()
same_year = now.replace(month=1, day=2, hour=9, minute=5, second=0)
if same_year.date() == now.date():
    same_year = now.replace(month=6, day=2, hour=9, minute=5, second=0)
other_year = now.replace(year=now.year - 1, month=3, day=4,
                         hour=9, minute=5, second=0)

check('today is a time',
      notes.short_date(now.timestamp()) == now.strftime('%H:%M'),
      notes.short_date(now.timestamp()))
check('this year is a day and a month',
      notes.short_date(same_year.timestamp()) == same_year.strftime('%d.%m.'),
      notes.short_date(same_year.timestamp()))
check('older carries the year',
      notes.short_date(other_year.timestamp()) ==
      other_year.strftime('%d.%m.%y'),
      notes.short_date(other_year.timestamp()))

section('4) The overview is sorted, newest first')
for path in NOTES_DIR.glob('*.txt'):
    path.unlink()

base = now.timestamp()
write('old.txt', 'Oldest\n', base - 3000)
write('middle.txt', 'In between\n', base - 2000)
write('new.txt', 'Newest\n', base - 1000)

found = notes.overview()
check('three entries', len(found) == 3, len(found))
check('newest first',
      [note.title for note in found] == ['Newest', 'In between', 'Oldest'],
      [note.title for note in found])
check('the path comes along', found[0].path == NOTES_DIR / 'new.txt')
check('the time comes along', abs(found[0].changed - (base - 1000)) < 1)
check('latest() agrees with the overview', notes.latest() == found[0].path)

section('5) Umlauts and emoji')
check('umlauts survive',
      notes.title(write('u.txt', 'Rückfahrkarte für Grünkohl\n')) ==
      'Rückfahrkarte für Grünkohl')
check('an emoji is a title too',
      notes.title(write('v.txt', 'Einkauf \U0001f34e\U0001f956\n')) ==
      'Einkauf \U0001f34e\U0001f956')
# A family emoji is several code points joined by zero-width joiners. Cutting
# at 200 characters can land in the middle of one; that is cosmetic -- what
# matters is that it does not raise.
long_emoji = '\U0001f468\u200d\U0001f469\u200d\U0001f467' * 100
cut = notes.title(write('w.txt', long_emoji + '\n'))
check('a cut-up emoji does not raise', len(cut) == notes.TITLE_MAX, len(cut))

section('6) A note that vanishes between listing and opening')
gone = write('x.txt', 'here for now\n')
gone.unlink()
check('load gives nothing back, not an exception', notes.load(gone) == '')
check('title likewise', notes.title(gone) == '')

section('7) The trash, not oblivion')
trash_dir = Path(GLib.get_user_data_dir()) / 'Trash' / 'files'
before_trash = set(trash_dir.iterdir()) if trash_dir.is_dir() else set()

doomed = write(f'zettel-test-trash-{os.getpid()}.txt', 'wegwerfen\n')
check('trash reports success', notes.trash(doomed) is True)
check('the note is out of the folder', not doomed.exists())

after_trash = set(trash_dir.iterdir()) if trash_dir.is_dir() else set()
landed = after_trash - before_trash
check('it landed in the trash', len(landed) == 1, sorted(p.name for p in landed))
for leftover in landed:          # leave the real trash as we found it
    leftover.unlink(missing_ok=True)
    info = (trash_dir.parent / 'info' / (leftover.name + '.trashinfo'))
    info.unlink(missing_ok=True)

check('trashing what is already gone counts as done',
      notes.trash(doomed) is True)

section('8) Nowhere to put it is not a licence to delete')
stubborn = write('keep-me.txt', 'nicht loeschen\n')


class Refuses:
    def trash(self, _cancellable):
        raise GLib.Error('no trash on this filesystem')


real_new_for_path = notes.Gio.File.new_for_path
notes.Gio.File.new_for_path = lambda _p: Refuses()
try:
    check('reports failure', notes.trash(stubborn) is False)
    check('and the note is still there', stubborn.exists())
finally:
    notes.Gio.File.new_for_path = real_new_for_path

section('9) A folder we may not read is not an error either')
NOTES_DIR.chmod(0o000)
try:
    check('overview is empty', notes.overview() == [])
    check('latest is None', notes.latest() is None)
finally:
    NOTES_DIR.chmod(0o700)

section('10) No folder is not an error')
for path in NOTES_DIR.glob('*.txt'):
    path.unlink()
NOTES_DIR.rmdir()
check('overview is empty', notes.overview() == [])
check('all_notes is empty', notes.all_notes() == [])
check('latest is None', notes.latest() is None)

report(NOTES_DIR)
