"""Tray icon, panel window, polling, toasts, autostart and single instance."""
import ctypes
import getpass
import json
import logging
import os
import sys
import time
import winreg
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Property, QObject, QPoint, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import device, hotkeys, lanmouse

APP_NAME = 'Marekov Easy MX Master Switcher'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'MarekovEasyMxMasterSwitcher'
INSTANCE = f'MarekovEasyMxMasterSwitcher-{getpass.getuser()}'
HERE = os.path.dirname(os.path.abspath(__file__))

# The user's Omarchy theme; the one place colours are defined (QML gets them as `theme`).
THEME = {
    'background': '#2c2525',
    'darkBackground': '#211b1b',
    'foreground': '#e6d9db',
    'dim': '#72696a',
    'accent': '#f38d70',
    'selection': '#403e41',
    'rowBorder': '#33e6d9db',  # foreground at 20 %
    'red': '#fd6883',
}
MOUSE, MOUSE_OFF = '\U000F037D', '\U000F037E'

log = logging.getLogger(__name__)


class Backend(QObject):
    """What the QML panel sees: the mx-host-style state as JSON, plus switching."""
    stateJsonChanged = Signal()
    switchingChanged = Signal()
    notify = Signal(str, str)
    switched = Signal()
    hotkey = Signal(int)  # emitted from the hotkey thread, delivered on the GUI thread
    _statusReady = Signal(str)

    def __init__(self):
        super().__init__()
        self._state = json.dumps(device.cached_state())
        self._switching = False
        self._polling = False
        self._worker = ThreadPoolExecutor(1)  # one thread, so HID requests never overlap
        self._statusReady.connect(self._set_state)
        self.switched.connect(self._switched)
        self.hotkey.connect(self.switchTo)

    @Property(str, notify=stateJsonChanged)
    def stateJson(self):
        return self._state

    @Property(bool, notify=switchingChanged)
    def switching(self):
        return self._switching

    def state(self):
        return json.loads(self._state)

    @Slot()
    def refresh(self):
        if self._polling:
            return
        self._polling = True
        self._worker.submit(lambda: self._statusReady.emit(json.dumps({**device.status(), 'lanMouse': lanmouse.running()})))

    @Slot(bool)
    def setLanMouse(self, on):
        def run():
            try:
                lanmouse.set_running(on)
            except OSError as e:
                self.notify.emit('lan-mouse could not start', str(e))
        self._worker.submit(run)
        self._polling = False  # a poll already queued may predate the toggle; queue another
        self.refresh()

    def _set_state(self, raw):
        self._polling = False
        if raw != self._state:
            self._state = raw
            self.stateJsonChanged.emit()

    @Slot(int)
    def switchTo(self, channel):
        if self._switching:
            return
        self._switching = True
        self.switchingChanged.emit()

        def run():
            try:
                device.switch(channel, self.notify.emit)
            finally:
                self.switched.emit()
        self._worker.submit(run)

    def _switched(self):
        self._switching = False
        self.switchingChanged.emit()
        self.refresh()


def tray_icon(state):
    """Mouse glyph, light on transparent, with the channel number; dimmed mouse-off while away."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        def glyph(text, box, bold=False):
            """Draw text scaled so its outline fills box (x, y, w, h as fractions of size)."""
            font = QFont('JetBrainsMono Nerd Font')
            font.setBold(bold)
            font.setPixelSize(100)
            path = QPainterPath()
            path.addText(0, 0, font, text)
            src, dst = path.boundingRect(), QRectF(*(v * size for v in box))
            scale = min(dst.width() / src.width(), dst.height() / src.height())
            p.save()
            p.translate(dst.center())
            p.scale(scale, scale)
            p.translate(-src.center())
            p.fillPath(path, QColor(THEME['foreground']))
            p.restore()

        if state['connected']:
            glyph(str(state['current']), (0, 0.14, 0.42, 0.72), bold=True)
            glyph(MOUSE, (0.48, 0.08, 0.52, 0.84))
        else:
            p.setOpacity(0.5)
            glyph(MOUSE_OFF, (0.06, 0.06, 0.88, 0.88))
        p.end()
        icon.addPixmap(pixmap)
    return icon


def tooltip(state):
    names = state['names']
    name = lambda channel: names.get(str(channel)) or f'device {channel}'
    if state['connected']:
        return f'MX Master 4 · {name(state["current"])}'
    return 'MX Master 4 · ' + (f'away on {name(state["awayTo"])}' if state['awayTo'] else 'not connected')


def autostart_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    return f'"{pythonw}" "{os.path.join(os.path.dirname(HERE), "main.py")}"'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, RUN_VALUE)[0])
    except OSError:
        return False


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


def ask_running_instance_to_open():
    """True if another instance is running; it is then asked to open its panel."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE)
    if not socket.waitForConnected(500):
        return False
    ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: let it bring the panel to the front
    socket.write(b'open')
    socket.waitForBytesWritten(500)
    return True


def main():
    os.makedirs(device.APP_DIR, exist_ok=True)
    logging.basicConfig(filename=os.path.join(device.APP_DIR, 'app.log'), level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(os.path.join(HERE, 'app.ico')))
    app.setQuitOnLastWindowClosed(False)
    if ask_running_instance_to_open():
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE)
    server.listen(INSTANCE)

    for font in ('JetBrainsMonoNerdFont-Regular.ttf', 'JetBrainsMonoNerdFont-Bold.ttf'):
        QFontDatabase.addApplicationFont(os.path.join(HERE, 'fonts', font))

    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.rootContext().setContextProperty('theme', THEME)
    engine.load(os.path.join(HERE, 'Panel.qml'))
    panel = engine.rootObjects()[0]

    tray = QSystemTrayIcon()
    menu = QMenu()
    menu.addAction('Refresh', backend.refresh)
    autostart = QAction('Start with Windows', menu, checkable=True, checked=autostart_enabled())
    autostart.toggled.connect(set_autostart)
    menu.addAction(autostart)
    menu.addSeparator()
    menu.addAction('Quit', app.quit)
    tray.setContextMenu(menu)

    last_closed = [0.0]

    def place_panel():
        # Bottom-right corner of the work area, i.e. just above the tray (or below a top taskbar).
        screen = app.screenAt(tray.geometry().center()) or app.primaryScreen()
        area, full, margin = screen.availableGeometry(), screen.geometry(), 12
        x = area.right() - panel.width() - margin
        y = area.top() + margin if area.top() > full.top() else area.bottom() - panel.height() - margin
        panel.setPosition(QPoint(x, y))

    def open_panel():
        place_panel()
        panel.setProperty('shown', True)

    def toggle_panel():
        if panel.property('shown'):
            panel.setProperty('shown', False)
        elif time.monotonic() - last_closed[0] > 0.4:  # this click is what just closed it
            open_panel()

    poll = QTimer(interval=6000)
    poll.timeout.connect(backend.refresh)

    def on_shown():
        shown = panel.property('shown')
        if not shown:
            last_closed[0] = time.monotonic()
        poll.setInterval(2000 if shown else 6000)
        if shown:
            backend.refresh()

    panel.shownChanged.connect(on_shown)
    panel.heightChanged.connect(lambda: panel.property('shown') and place_panel())

    def on_state():
        state = backend.state()
        tray.setIcon(tray_icon(state))
        tray.setToolTip(tooltip(state))

    backend.stateJsonChanged.connect(on_state)
    backend.notify.connect(lambda title, body: tray.showMessage(title, body, tray.icon(), 4000))
    backend.switched.connect(lambda: panel.setProperty('shown', False))
    tray.activated.connect(lambda reason: reason == QSystemTrayIcon.Trigger and toggle_panel())
    server.newConnection.connect(lambda: (server.nextPendingConnection(), open_panel()))
    hotkeys.start(backend.hotkey.emit)

    on_state()
    tray.show()
    poll.start()
    backend.setLanMouse(True)  # on at login; the panel switch turns it off for this session
    return app.exec()
