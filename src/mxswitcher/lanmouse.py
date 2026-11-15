"""Start / stop the lan-mouse daemon (https://github.com/feschber/lan-mouse) that receives the Linux
machine's mouse and keyboard. Installed as described in README → Windows lan-mouse setup."""
import os
import subprocess

EXE = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'lan-mouse', 'lan-mouse.exe')
NAME = os.path.basename(EXE)
HIDDEN = subprocess.CREATE_NO_WINDOW  # it is a console program


def running():
    out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {NAME}', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True, creationflags=HIDDEN).stdout
    return NAME.lower() in out.lower()


def set_running(on):
    if on and not running():
        subprocess.Popen([EXE, 'daemon'], cwd=os.path.dirname(EXE), creationflags=HIDDEN,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif not on:
        subprocess.run(['taskkill', '/IM', NAME, '/F'], capture_output=True, creationflags=HIDDEN)
