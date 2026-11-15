"""HID++ 2.0 access to the MX Master 4: read and switch the Easy-Switch channel.

Windows port of reference/linux/mx-host.py. Only device discovery differs: instead of
hidraw nodes we open the HID top-level collection that carries HID++ long reports.
"""
import logging
import time

import hid

VENDOR_ID = 0x046D
PRODUCT_ID = 0xB042  # MX Master 4 over Bluetooth
HIDPP_COLLECTION = (0xFF43, 0x0202)  # vendor usage page / usage of the HID++ long-report collection
CHANGE_HOST = 0x1814
HOSTS_INFO = 0x1815
SOFTWARE_ID = 0x0B
DEVICE_INDEX = 0xFF  # Bluetooth-connected device

HidppError = (OSError, ValueError, TimeoutError, RuntimeError)

log = logging.getLogger(__name__)


class Unreachable(Exception):
    pass


class Mouse:
    """An open HID++ connection to the MX Master 4. Use as a context manager."""

    def __init__(self):
        candidates = hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if not candidates:
            raise Unreachable('not connected to this computer')
        # The HID++ collection first; the others normally reject a 0x11 report straight away.
        candidates.sort(key=lambda d: (d['usage_page'], d['usage']) != HIDPP_COLLECTION)
        reason = 'the mouse did not answer'
        for info in candidates:
            self.dev = hid.device()
            try:
                self.dev.open_path(info['path'])
                self.change_host = self._feature_index(CHANGE_HOST)
                if self.change_host:
                    log.debug('HID++ on usage %#06x/%#06x', info['usage_page'], info['usage'])
                    return
                reason = 'the mouse has no Easy-Switch feature'
            except HidppError as e:
                log.debug('usage %#06x/%#06x: %s', info['usage_page'], info['usage'], e)
                reason = str(e) or reason
            self.dev.close()
        raise Unreachable(reason)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.dev.close()

    def _request(self, feature, function, params=b'', reply=True):
        tag = (function << 4) | SOFTWARE_ID
        self.dev.write(bytes([0x11, DEVICE_INDEX, feature, tag, *params]).ljust(20, b'\0'))
        if not reply:
            return b''
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            report = bytes(self.dev.read(64, 200))
            if len(report) < 6 or report[0] != 0x11 or report[1] != DEVICE_INDEX:
                continue
            if report[2:5] == bytes([0xFF, feature, tag]):
                raise RuntimeError(f'HID++ error {report[5]:#x}')
            if report[2:4] == bytes([feature, tag]):
                return report[4:]
        raise TimeoutError('the mouse did not answer')

    def _feature_index(self, feature):
        return self._request(0x00, 0, feature.to_bytes(2, 'big'))[0]

    def channels(self):
        """(channel count, current channel), channels numbered from 1."""
        info = self._request(self.change_host, 0)
        return info[0], info[1] + 1

    def switch_to(self, channel):
        # The mouse drops this connection immediately, so no reply comes back.
        self._request(self.change_host, 1, [channel - 1], reply=False)

    def names(self, count):
        """{'1': name, ...} of the paired computers; {} when the mouse can't tell."""
        try:
            hosts_info = self._feature_index(HOSTS_INFO)
            if not hosts_info or not self._request(hosts_info, 0)[0] & 0x01:
                return {}
            names = {}
            for host in range(count):
                info = self._request(hosts_info, 1, [host])
                paired, length = info[1], info[4]
                name = b''
                while paired and len(name) < length:
                    chunk = self._request(hosts_info, 3, [host, len(name)])[2:2 + min(14, length - len(name))]
                    if not chunk:
                        break
                    name += chunk
                names[str(host + 1)] = name.split(b'\0')[0].decode('utf-8', 'replace').strip()
            return names
        except HidppError:
            return {}
