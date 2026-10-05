#!/usr/bin/python3
'''Set Zettel up on this machine, or take it back off again.

    /usr/bin/python3 install.py
    /usr/bin/python3 install.py --uninstall

Everything it asks has a default; Enter accepts it. Nothing here needs root,
and nothing outside the user's own home is touched.
'''

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKAGE = 'zettel'
APP_ID = 'io.github.julianbvw.Zettel'
PYTHON = '/usr/bin/python3'

INSTALL_DIR = Path.home() / '.local' / 'share' / 'zettel'
CONFIG_DIR = Path.home() / '.config' / 'zettel'
CONFIG_FILE = CONFIG_DIR / 'config.json'
AUTOSTART = Path.home() / '.config' / 'autostart' / 'zettel.desktop'

CUSTOM_SCHEMA = 'org.cinnamon.desktop.keybindings.custom-keybinding'
CUSTOM_PATH = '/org/cinnamon/desktop/keybindings/custom-keybindings/'
LIST_SCHEMA = 'org.cinnamon.desktop.keybindings'
SHORTCUT_SCHEMAS = (
    'org.cinnamon.desktop.keybindings.wm',
    'org.cinnamon.desktop.keybindings.media-keys',
    'org.cinnamon.muffin.keybindings',
)

BLUR_UUID = 'BlurCinnamon@klangman'
MARGIN = 24
MIN_WIDTH, MAX_WIDTH = 420, 700
MIN_HEIGHT = 400

DESKTOP_ENTRY = '''[Desktop Entry]
Type=Application
Name=Zettel
Comment=Scratchpad, resident so the shortcut is instant
Exec={python} -m {package} --daemon
Path={path}
Terminal=false
X-GNOME-Autostart-enabled=true
'''

SHORTCUTS = (
    ('Zettel: show or hide', 'toggle'),
    ('Zettel: new note / discard', 'scratch'),
)


# -- the part that only computes, so it can be tested ---------------------

def default_notes_dir(lang):
    '''The folder name is the one thing here that is in the user's language.'''
    german = (lang or '').lower().startswith('de')
    return Path.home() / ('Notizen' if german else 'Notes')


def suggested_size(work_width, work_height):
    '''A window a fifth of the screen wide, within reason.

    A fifth is right on a 2560 px screen and absurd on a 5120 one, so it is
    bounded at both ends -- and then bounded again by the screen itself, for
    the case where even the lower bound does not fit.
    '''
    width = min(MAX_WIDTH, max(MIN_WIDTH, work_width // 5))
    height = max(MIN_HEIGHT, work_height * 2 // 3)
    width = min(width, max(1, work_width - 2 * MARGIN))
    height = min(height, max(1, work_height - 2 * MARGIN))
    return width, height


def next_custom_slot(taken):
    '''The lowest customN not in `taken`.

    Searched, not guessed: slot custom0 may well hold someone else's shortcut,
    and writing over it would be rude at best.
    '''
    used = set()
    for name in taken:
        if name.startswith('custom') and name[len('custom'):].isdigit():
            used.add(int(name[len('custom'):]))
    number = 0
    while number in used:
        number += 1
    return f'custom{number}'


def accelerator_taken(accelerator, bindings):
    '''Who already holds this accelerator, or None.

    Whole accelerators are compared, never substrings: <Alt>F4 is window-close
    and has nothing to do with a bare F4.
    '''
    for holder, held in bindings.items():
        if accelerator in held:
            return holder
    return None


# -- asking ---------------------------------------------------------------

def ask(question, default):
    answer = input(f'  {question} [{default}]: ').strip()
    return answer or default


def ask_yes(question, default=True):
    hint = 'Y/n' if default else 'y/N'
    answer = input(f'  {question} [{hint}]: ').strip().lower()
    if not answer:
        return default
    return answer.startswith(('y', 'j'))


def ask_choice(question, options, default):
    print(f'  {question}')
    for number, option in enumerate(options, 1):
        mark = ' (default)' if option == default else ''
        print(f'    {number}) {option}{mark}')
    answer = input(f'  1-{len(options)} [{options.index(default) + 1}]: ').strip()
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return default


# -- looking around -------------------------------------------------------

def schema_keys(schema_id):
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(schema_id, True)
    return schema.list_keys() if schema is not None else []


def current_bindings():
    '''Every accelerator the desktop already holds: holder -> list.'''
    bindings = {}
    for schema_id in SHORTCUT_SCHEMAS:
        try:
            settings = Gio.Settings.new(schema_id)
        except Exception:
            continue
        for key in schema_keys(schema_id):
            value = settings.get_value(key)
            if value.get_type_string() == 'as':
                bindings[f'{schema_id} {key}'] = list(value.unpack())

    for slot in Gio.Settings.new(LIST_SCHEMA).get_strv('custom-list'):
        settings = custom_settings(slot)
        if APP_ID in settings.get_string('command'):
            # Our own, from an earlier run. Reinstalling should not report a
            # conflict with itself.
            continue
        label = settings.get_string('name') or slot
        bindings[f'custom shortcut "{label}"'] = settings.get_strv('binding')
    return bindings


def custom_settings(slot):
    return Gio.Settings.new_with_path(CUSTOM_SCHEMA, f'{CUSTOM_PATH}{slot}/')


def work_area():
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor() or display.get_monitor(0)
    area = monitor.get_workarea()
    return area.width, area.height


def blur_available():
    '''Is BlurCinnamon installed and switched on?'''
    folders = (Path.home() / '.local/share/cinnamon/extensions' / BLUR_UUID,
               Path('/usr/share/cinnamon/extensions') / BLUR_UUID)
    if not any(folder.is_dir() for folder in folders):
        return False
    try:
        enabled = Gio.Settings.new('org.cinnamon').get_strv('enabled-extensions')
    except Exception:
        return False
    return BLUR_UUID in enabled


def system_python_has_gi():
    '''The autostart entry runs /usr/bin/python3, so that one needs gi.

    On this machine `python3` in PATH is miniforge and has no gi at all; the
    failure would be a ModuleNotFoundError at login, long after anyone is
    watching.
    '''
    try:
        subprocess.run([PYTHON, '-c', 'import gi'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


# -- doing ----------------------------------------------------------------

def copy_package(target):
    destination = target / PACKAGE
    if destination.exists():
        # Emptied first, so files dropped from the project do not live on --
        # but only once it has been established that this really is ours.
        if not (destination / '__main__.py').is_file():
            sys.exit(f'{destination} exists and is not a Zettel install. '
                     'Refusing to touch it.')
        shutil.rmtree(destination)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / PACKAGE, destination,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def write_config(settings):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=2) + '\n',
                           encoding='utf-8')


def write_autostart(run_from):
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        DESKTOP_ENTRY.format(python=PYTHON, package=PACKAGE, path=run_from),
        encoding='utf-8')


def install_shortcuts(accelerators):
    '''Write the shortcuts, custom-list last.

    That order matters: csd-media-keys only re-reads the sub-keys when the
    list changes. Set the list first and it reads empty entries -- which is
    exactly what went wrong on 18.09.
    '''
    # Any of ours from an earlier run go first, or installing twice would
    # leave the shortcut bound in two places at once.
    remove_shortcuts()

    listing = Gio.Settings.new(LIST_SCHEMA)
    slots = list(listing.get_strv('custom-list'))

    for (label, action), accelerator in zip(SHORTCUTS, accelerators):
        slot = next_custom_slot(slots)
        settings = custom_settings(slot)
        settings.set_string('name', label)
        settings.set_string('command',
                            f'gapplication action {APP_ID} {action}')
        settings.set_strv('binding', [accelerator])
        slots.append(slot)

    Gio.Settings.sync()
    listing.set_strv('custom-list', slots)   # last, always
    Gio.Settings.sync()
    return slots


def remove_shortcuts():
    '''Drop every custom shortcut that points at us. The list goes last.'''
    listing = Gio.Settings.new(LIST_SCHEMA)
    keep, dropped = [], []
    for slot in listing.get_strv('custom-list'):
        settings = custom_settings(slot)
        if APP_ID in settings.get_string('command'):
            for key in ('name', 'command', 'binding'):
                settings.reset(key)
            dropped.append(slot)
        else:
            keep.append(slot)
    Gio.Settings.sync()
    listing.set_strv('custom-list', keep)
    Gio.Settings.sync()
    return dropped


def stop_daemon():
    subprocess.run(['gapplication', 'action', APP_ID, 'quit'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_daemon(run_from):
    subprocess.Popen([PYTHON, '-m', PACKAGE, '--daemon'], cwd=str(run_from),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


# -- the two commands -----------------------------------------------------

def install(in_place):
    print('\nZettel\n')

    if not system_python_has_gi():
        sys.exit(f'{PYTHON} cannot import gi, and that is what the autostart '
                 'entry will run.\nOn Mint: sudo apt install python3-gi '
                 'gir1.2-gtksource-4')

    suggestion = default_notes_dir(os.environ.get('LANG', ''))
    notes_dir = Path(ask('Notes folder', suggestion)).expanduser()

    width, height = suggested_size(*work_area())
    size = ask('Window size', f'{width}x{height}')
    try:
        width, height = (int(part) for part in size.lower().split('x', 1))
    except ValueError:
        print(f'    Not a size, keeping {width}x{height}.')

    corner = ask_choice('Which corner does it start in?',
                        ['bottom-right', 'bottom-left', 'top-right', 'top-left'],
                        'bottom-right')

    bindings = current_bindings()
    accelerators = []
    for (label, _action), default in zip(SHORTCUTS, ('F4', '<Shift>F4')):
        while True:
            accelerator = ask(f'Shortcut for {label.split(": ")[1]}', default)
            holder = accelerator_taken(accelerator, bindings)
            if holder is None:
                break
            print(f'    {accelerator} is already held by {holder}.')
            if ask_yes('    Use it anyway?', False):
                break
        accelerators.append(accelerator)

    blur = blur_available()
    print(f'\n  BlurCinnamon is {"installed and on" if blur else "not in use"}.')
    blur = ask_yes('  Assume a blurred backdrop?', blur)

    run_from = HERE if in_place else INSTALL_DIR
    print()
    if in_place:
        print(f'  Running from {run_from} (--in-place)')
    else:
        copy_package(INSTALL_DIR)
        print(f'  Copied the package to {INSTALL_DIR / PACKAGE}')

    write_config({'notes_dir': str(notes_dir), 'width': width,
                  'height': height, 'corner': corner, 'blur': blur})
    print(f'  Wrote {CONFIG_FILE}')

    notes_dir.mkdir(parents=True, exist_ok=True)
    print(f'  Notes folder {notes_dir}')

    write_autostart(run_from)
    print(f'  Wrote {AUTOSTART}')

    slots = install_shortcuts(accelerators)
    print(f'  Shortcuts {", ".join(accelerators)} '
          f'on {", ".join(slots[-len(accelerators):])}')

    stop_daemon()
    start_daemon(run_from)
    print(f'\n  Running. Press {accelerators[0]}.')

    if blur:
        print(BLUR_HINT)
    print()


BLUR_HINT = '''
  For the blur itself, in BlurCinnamon's settings under "Component specific
  settings", switch on "Enable window effects" and add an entry:

      Application           Zettel
      Custom                on
      Opacity               100      (fading the window would fade the text)
      Dim                   0        (Zettel brings its own 72 %)
      Background            Dual Kawase dynamic blur
      Intensity             18
      Saturation            125
      Corner Radius         16       (same as the window's own)
      Rounded Top / Bottom  both on
'''


def uninstall():
    print('\nZettel -- taking it back off\n')

    notes_dir = None
    try:
        notes_dir = json.loads(CONFIG_FILE.read_text(encoding='utf-8')).get(
            'notes_dir')
    except (OSError, ValueError):
        pass

    stop_daemon()

    dropped = remove_shortcuts()
    print(f'  Shortcuts removed: {", ".join(dropped) if dropped else "none"}')

    for path in (AUTOSTART,):
        if path.exists():
            path.unlink()
            print(f'  Removed {path}')

    for folder in (CONFIG_DIR, INSTALL_DIR):
        if folder.is_dir():
            shutil.rmtree(folder)
            print(f'  Removed {folder}')

    print(f'\n  Your notes are still in {notes_dir or "the notes folder"}. '
          'Nothing in there was touched.\n')


def main(argv):
    if '--uninstall' in argv:
        uninstall()
    else:
        install(in_place='--in-place' in argv)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
