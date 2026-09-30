# Zettel

A scratchpad for the Linux desktop. Not an editor.

*Zettel* is German for a slip of paper — the kind you scribble on and throw
away, or keep on your desk for a fortnight.

`F4` brings it up, `F4` puts it away. In between, it still says whatever it
said last time.

## Why

For the note that lives two minutes, and for the one that stays two weeks.
For the error message you want to look at properly. And for stripping the
formatting off text you copied from a web page, before it ends up somewhere
else.

None of that warrants a text editor. An editor manages files — a scratchpad
has none. So there is no save dialog, no file picker, and no question when
you close it.

## Keys

| Key | |
|---|---|
| `F4` | open → list of notes · when open: close |
| `1`–`9` | open that note |
| `` ` `` | new note |
| `Shift`+`F4` | straight into a new note, skipping the list |
| `Alt`+`←` | back to the list |
| `Esc` | close |

Leaving saves the note if there is anything in it, and drops it if there
isn't. Holding `Shift` always discards. Emptying a note and closing it deletes
it — that is the only way to delete, and it needs no button.

## Why it stays running

A program that *starts* when you press a key takes half a second to appear,
which is exactly long enough to lose the thought you meant to write down.
Zettel therefore runs in the background and only shows a window.

That costs about 15 MB and no measurable CPU time while idle. A single browser
tab uses thirty-eight times as much.

## Built with

Python 3, GTK 3, GtkSourceView — nothing a Linux Mint system doesn't already
have.

Notes are stored as plain text in `~/Notizen/`.

## Status

Work in progress. Writing, saving and reopening notes works; the window is
plain and holds one note at a time. A list to pick between notes comes next,
and the styling after that.
