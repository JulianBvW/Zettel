'''The little bit of scaffolding both test scripts share.

No pytest: the whole point of Zettel is that it needs nothing installed, and
a test suite that breaks that promise is a strange way to defend it. Run a
test file directly; it exits non-zero as soon as one check fails.
'''

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_ok = 0
_failed = 0


def check(name, condition, detail=''):
    global _ok, _failed
    if condition:
        _ok += 1
        print(f'  PASS  {name}')
    else:
        _failed += 1
        print(f'  FAIL  {name}  {detail}')


def section(title):
    print(f'\n{title}')


def sandbox():
    '''A notes folder of our own, so ~/Notizen is never touched.

    Patches config.NOTES_DIR, which notes.py reads at call time rather than
    import time -- that is what makes this possible at all.
    '''
    from zettel import config
    folder = Path(tempfile.mkdtemp(prefix='zettel-test-'))
    config.NOTES_DIR = folder
    return folder


def report(folder=None):
    if folder is not None:
        shutil.rmtree(folder, ignore_errors=True)
    print(f'\n===  {_ok} passed, {_failed} failed  ===')
    sys.exit(1 if _failed else 0)
