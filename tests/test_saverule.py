'''Drives the EditorView directly -- no keyboard, no D-Bus, no window.

Needs a display, because a GtkSource.View has to be built:
    DISPLAY=:0 /usr/bin/python3 tests/test_saverule.py
'''

import time

from harness import check, report, sandbox, section

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk  # noqa: E402

NOTES_DIR = sandbox()  # must happen before notes/editor are used

from zettel import notes  # noqa: E402
from zettel.editor import EditorView  # noqa: E402


def files():
    return sorted(p.name for p in NOTES_DIR.glob('*.txt'))


def pump(seconds):
    '''Let the main loop run, so the autosave timer actually fires.'''
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


ed = EditorView(verbose=False)


def set_text(text):
    ed.view.get_buffer().set_text(text)


section('1) A new note with content -- the file appears on leaving')
ed.open_new()
set_text('Shopping\nMilk, bread')
check('no file yet', files() == [], files())
ed.commit()
check('exactly one file', len(files()) == 1, files())
first = NOTES_DIR / files()[0]
check('content is right', notes.load(first) == 'Shopping\nMilk, bread')

section('2) open_latest loads it back')
ed.open_latest()
check('text is there again', ed.text == 'Shopping\nMilk, bread', repr(ed.text))

section('3) A note FROM DISK: undo must not empty it')
# As after a restart: the file exists but has never been in a buffer.
fresh = EditorView(verbose=False)
fresh.open_latest()
buffer = fresh.view.get_buffer()
check('text loaded', fresh.text == 'Shopping\nMilk, bread', repr(fresh.text))
check('can_undo is False', not buffer.can_undo())

section('3b) Typed text SURVIVES close and reopen (the buffer cache)')
ed.open_new()
buffer = ed.view.get_buffer()
buffer.insert_at_cursor('First line')
ed.commit()                 # like F4 closing
ed.open_latest()            # like F4 opening
check('same buffer', ed.view.get_buffer() is buffer)
check('can still undo', ed.view.get_buffer().can_undo())
ed.commit(discard=True)
ed.open_latest()            # back on the note from step 1

section('4) Emptying it and leaving deletes the note')
set_text('')
ed.commit()
check('file is gone', files() == [], files())

section('5) Whitespace alone counts as empty')
ed.open_new()
set_text('   \n\t\n  ')
ed.commit()
check('nothing was created', files() == [], files())

section('6) Shift+F4 discards even with content')
ed.open_new()
set_text('Throwaway text from the clipboard')
ed.commit(discard=True)
check('nothing was created', files() == [], files())

section('7) Discarding an existing note with Shift+F4')
ed.open_new()
set_text('stays for now')
ed.commit()
check('created', len(files()) == 1, files())
ed.open_latest()
ed.commit(discard=True)
check('deleted', files() == [], files())

section('8) Autosave writes on its own after the pause')
ed.open_new()
set_text('typing away')
check('nothing immediately', files() == [], files())
pump(1.0)
check('written after 1 s', len(files()) == 1, files())
check('content is right', notes.load(NOTES_DIR / files()[0]) == 'typing away')

section('9) Autosave never deletes, not even on empty text')
set_text('')
pump(1.0)
check('file still alive', len(files()) == 1, files())
check('old content kept',
      notes.load(NOTES_DIR / files()[0]) == 'typing away')
ed.commit()
check('only commit deletes', files() == [], files())

section('10) Undo after real typing works')
ed.open_new()
buffer = ed.view.get_buffer()
buffer.insert_at_cursor('abc')
buffer.insert_at_cursor('def')
check('can_undo', buffer.can_undo())
buffer.undo()
check('one step back', ed.text == 'abc', repr(ed.text))
check('can_redo', buffer.can_redo())
buffer.redo()
check('forward again', ed.text == 'abcdef', repr(ed.text))
ed.commit(discard=True)

section('11) Two notes in the same second do not collide')
one = notes.new_path()
notes.save(one, 'one')
two = notes.new_path()
notes.save(two, 'two')
check('two different files', one != two and len(files()) == 2, files())
check('latest() is one of them', notes.latest() in (one, two))

section('12) Looking at a note does not move it to the top')
# The list sorts by modification time. If a plain look rewrote the file, any
# note you opened out of curiosity would jump to position 1.
for leftover in NOTES_DIR.glob('*.txt'):
    leftover.unlink()

older = notes.new_path()
notes.save(older, 'the one we look at')
import os  # noqa: E402  -- only needed here, to age a file on purpose
long_ago = time.time() - 5000
os.utime(older, (long_ago, long_ago))
before = older.stat().st_mtime

viewer = EditorView(verbose=False)
viewer.open_note(older)
check('content is there', viewer.text == 'the one we look at')
viewer.commit()                       # like Alt+Left, without typing a thing
check('file untouched', older.stat().st_mtime == before,
      f'{older.stat().st_mtime} != {before}')
check('still there', older.exists())

section('13) Typing in it does move it')
viewer.view.get_buffer().insert_at_cursor('!')
viewer.commit()
check('written now', older.stat().st_mtime > before)
check('content updated', notes.load(older) == 'the one we look at!')

report(NOTES_DIR)
