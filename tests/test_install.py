'''The parts of the installer that only compute.

    /usr/bin/python3 tests/test_install.py

Copying files, gsettings and the autostart entry touch the real system and
stay a check by hand.
'''

from pathlib import Path

from harness import check, report, section

import install  # noqa: E402

section('1) The notes folder follows the language')
check('German', install.default_notes_dir('de_DE.UTF-8') ==
      Path.home() / 'Notizen')
check('German, lower case', install.default_notes_dir('de') ==
      Path.home() / 'Notizen')
check('English', install.default_notes_dir('en_US.UTF-8') ==
      Path.home() / 'Notes')
check('something else', install.default_notes_dir('fr_FR.UTF-8') ==
      Path.home() / 'Notes')
check('nothing set', install.default_notes_dir('') == Path.home() / 'Notes')
check('not even a string', install.default_notes_dir(None) ==
      Path.home() / 'Notes')

section('2) The size follows the screen, within reason')
check('this machine, 2560x1035', install.suggested_size(2560, 1035) ==
      (512, 690), install.suggested_size(2560, 1035))
check('1920 wide hits the lower bound',
      install.suggested_size(1920, 1030)[0] == install.MIN_WIDTH,
      install.suggested_size(1920, 1030))
check('5120 wide hits the upper bound',
      install.suggested_size(5120, 1440)[0] == install.MAX_WIDTH,
      install.suggested_size(5120, 1440))
tiny = install.suggested_size(640, 480)
check('a tiny screen still fits the screen',
      tiny[0] <= 640 and tiny[1] <= 480, tiny)
check('and leaves room for the margin',
      tiny[0] <= 640 - 2 * install.MARGIN, tiny)

section('3) The shortcut slot is searched, not guessed')
check('nothing taken', install.next_custom_slot([]) == 'custom0')
check('taken in order',
      install.next_custom_slot(['custom0', 'custom1']) == 'custom2')
check('a gap is used',
      install.next_custom_slot(['custom0', 'custom2']) == 'custom1')
check('out of order',
      install.next_custom_slot(['custom7', 'custom0']) == 'custom1')
check('something that is not a slot',
      install.next_custom_slot(['custom0', 'whatever']) == 'custom1')

section('4) Whole accelerators, never substrings')
held = {'window close': ['<Alt>F4'],
        'screenshot': ['Print'],
        'nothing at all': []}
check('<Alt>F4 does not make F4 taken',
      install.accelerator_taken('F4', held) is None)
check('<Alt>F4 itself is taken',
      install.accelerator_taken('<Alt>F4', held) == 'window close')
check('Print is taken',
      install.accelerator_taken('Print', held) == 'screenshot')
check('<Shift>F4 is free',
      install.accelerator_taken('<Shift>F4', held) is None)

report()
