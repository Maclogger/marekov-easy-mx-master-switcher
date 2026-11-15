"""Global Ctrl + Alt + Shift + 1/2/3 via Win32 RegisterHotKey on a thread with its own message loop.

Hotkeys are matched on virtual-key codes, and Windows layouts (Slovak and Czech included) map the
physical number-row keys to VK_1… whatever characters they type, so this is layout-independent.
"""
import ctypes
import logging
import threading
from ctypes import wintypes

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY = 0x0312

log = logging.getLogger(__name__)


def start(callback, channels=(1, 2, 3)):
    """Call callback(channel) from a background thread whenever a hotkey is pressed."""
    def run():
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        for channel in channels:
            vk = ord('0') + channel
            if not user32.RegisterHotKey(None, channel, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, vk):
                log.warning('Ctrl+Alt+Shift+%s is taken (error %s)', channel, ctypes.get_last_error())
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                callback(msg.wParam)

    threading.Thread(target=run, name='hotkeys', daemon=True).start()
