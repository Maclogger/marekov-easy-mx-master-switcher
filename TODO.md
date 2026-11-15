# TODO — build the Windows app

> ✅ **Implemented** (see the checklist below). Day to day the mouse is shared with lan-mouse instead: [`LAN-MOUSE.md`](LAN-MOUSE.md).

This file is the brief for the agent implementing the Windows version. Read it fully, then
`reference/linux/mx-host.py` (protocol) and `reference/linux/Panel.qml` + the screenshots (look).
Work on the Windows machine itself, so you can run and test against the real mouse.

## Goal

A tray app for Windows 10/11, **"Marekov Easy MX Master Switcher"**, that:

1. shows in the tray whether the MX Master 4 is on this computer, and on which Easy-Switch channel;
2. opens a small panel from the tray icon listing channels 1–3 with the paired computers' names,
   and sends the mouse to the channel you click;
3. offers global shortcuts **Ctrl + Alt + Shift + 1 / 2 / 3** that do the same;
4. shows a toast notification saying where the mouse went;
5. looks like the Linux/Omarchy panel (see *Design*), not like a stock Windows dialog.

## Context you need

- The user has the same mouse paired on 3 channels. Channel names reported by the mouse today:
  `1 = NB1MRUC1`, `2 = MarekovArchLinux` (Linux, already has the working tool),
  `3 = MAREKOV-WINDOWS` (this Windows machine, most likely). Don't hard-code these — read them.
- The mouse is connected over **Bluetooth** (not a Bolt/Unifying receiver). Treat a receiver as a
  nice-to-have only.
- When the mouse is on another channel, Windows can't see it at all. The app must handle "away"
  gracefully and keep showing the last known channel names from a cache.
- The user types on a **Slovak (QWERTY)** layout, where the number row produces `+ ľ š …`, not
  digits. This broke the Linux shortcuts at first. Register the hotkeys so they work on the
  physical 1/2/3 keys regardless of layout, and verify it on this machine.

## Recommended stack

- **Python 3.12 + PySide6 (Qt Quick / QML)** — same UI technology as the Omarchy shell, so the
  reference `Panel.qml` translates closely.
- **`hidapi`** (`pip install hidapi`, module `hid`) for HID access.
- **PyInstaller** for a single-file `.exe` (`--onefile --windowed`, with an `.ico`).
- Global hotkeys via Win32 `RegisterHotKey` (through `ctypes`) and a native event filter, or a
  small dedicated thread with its own message loop. Avoid heavy keyboard-hook libraries.

If something here turns out not to work on Windows, pick an alternative and note why in the README.

## HID++ protocol (port from `reference/linux/mx-host.py`)

The device: Logitech vendor ID `0x046D`, MX Master 4 product ID **`0xB042`** over Bluetooth.

1. **Find the right HID interface.** Enumerate `hid.enumerate(0x046D, 0xB042)`. Windows splits the
   device into several top-level collections. Use the one carrying HID++ long reports: usage page
   `0xFF43` (vendor), usage `0x0202`, or whichever accepts a 20-byte report with ID `0x11`. Try each
   candidate and keep the first that answers the root feature query below. Log what you find.
2. **Report format** (long report, 20 bytes):
   `[0x11, device_index=0xFF, feature_index, (function << 4) | software_id, params…]`, padded with
   zeros. Software ID `0x0B` is fine. A reply echoes bytes 0–3 and carries the data from byte 4.
   An error reply has `byte2 = 0xFF`, `byte3 = feature_index`, `byte4 = function|swid`,
   `byte5 = error code`.
3. **Feature lookup:** root feature (index `0x00`), function 0, params = feature ID as 2 bytes big
   endian → reply byte 0 is that feature's index (0 = not supported).
4. **CHANGE_HOST `0x1814`:**
   - function 0 `getHostInfo` → `[host_count, current_host (0-based), …]`
   - function 1 `setCurrentHost(host 0-based)` → the mouse **disconnects immediately and never
     replies**. Send it without waiting for an answer.
5. **HOSTS_INFO `0x1815`** (computer names):
   - function 0 → byte 0 bit 0 set = names supported
   - function 1 `getHostInfo(host)` → `[host, status(paired?), bus, pages, name_length, name_max]`
   - function 3 `getHostFriendlyName(host, byte_offset)` → `[host, offset, up to 14 name bytes]`;
     loop until `name_length` bytes are read. Names are UTF-8, NUL-padded.
   - Names only change when a computer is re-paired: read them once per connection and cache them.
6. Use a timeout (~1.5 s) per request and skip unrelated input reports while waiting. The mouse
   also sends regular reports on the same interface.

Watch out for **Logi Options+**. If it is installed it talks to the same interface and may
interfere. Note in the README whether the app works alongside it or needs it closed.

## Behaviour

- **Polling:** check every ~6 s, every ~2 s while the panel is open. When the device isn't present,
  that's just an enumeration, which is cheap. When it is present, one `getHostInfo` request.
- **Cache** (`%LOCALAPPDATA%\MarekovEasyMxMasterSwitcher\state.json`): channel count, names, which
  channel is "this computer" (`here`), and `awayTo` (where this app last sent the mouse). The same
  fields as the Linux script's `~/.cache/mx-host.json`.
- **Switch flow:** show the toast first ("MX Master 4 → device 2", body "Moved to 2 · MarekovArchLinux"),
  then send `setCurrentHost`, then save `awayTo`. Switching to the current channel only shows
  "Already on this computer". If the mouse is away, show "MX Master 4 is not here" and do nothing.
- **Status texts** (same as Linux): `ON THIS COMPUTER · DEVICE 3`, `AWAY · ON MarekovArchLinux`,
  `NOT CONNECTED`, `SWITCHING…`.
- **Start with Windows:** a tray context-menu toggle (`HKCU\...\Run` entry). Also in the menu:
  *Refresh*, *Quit*.
- **Single instance:** a second launch just opens the panel of the running one.

## Design — match the Linux panel

Look at `reference/screenshots/panel-connected.png` and `panel-away.png`. Copy the layout,
spacing and tone, not Windows conventions.

- **Tray icon:** mouse glyph, light on transparent. While away, dimmed and crossed out. Ideally
  render the current channel number next to or onto the icon (a small badge), because the Linux
  bar shows `2 🖱`. Generate the icons at runtime from the font glyphs (`󰍽` mouse, `󰍾` mouse off,
  JetBrainsMono Nerd Font) or ship small PNG/ICO files.
- **Panel:** frameless, rounded only slightly (the Linux one is square with a 2 px accent border),
  appearing just above the tray / taskbar corner, closing on focus loss or Esc. No title bar, no
  shadows-heavy Fluent look.
  - Hero: big mouse glyph · **MX Master 4** (bold, title size) · status line in small caps-style
    uppercase, letter-spaced, dimmed.
  - Thin separator.
  - Section header **Easy-Switch**.
  - Three full-width bordered rows: icon (laptop `󰌢` for this computer, monitor `󰍹` for others),
    channel number, computer name, `(this computer)` suffix. The current channel is filled
    (selection colour). Hover or arrow keys put a cursor highlight on a row; Enter or click switches.
    While away, rows are disabled (≈55 % opacity) except the `awayTo` one stays highlighted.
  - Footer hint, dimmed caption: `Shortcut: Ctrl + Alt + Shift + 1 / 2 / 3`, or while away
    "The mouse is on another computer. Switch it back from there (or with its Easy-Switch button)."
  - Width ≈ 340 px at 100 % scaling; respect Windows DPI scaling.
- **Font:** JetBrainsMono Nerd Font (bundle it in the app; the Nerd Font glyphs are needed for icons).
- **Colours** (the user's current Omarchy theme; define them as named tokens in one place):

  | Token | Hex |
  |---|---|
  | background | `#2c2525` |
  | darkBackground | `#211b1b` |
  | foreground | `#e6d9db` |
  | dim / muted | `#72696a` |
  | accent (panel border, focus) | `#f38d70` |
  | selection (active row fill) | `#403e41` |
  | row border | foreground at ~20 % opacity |
  | red (errors) | `#fd6883` |

- **Motion:** subtle. Panel fades/scales in from 0.97 over ~180 ms, out over ~120 ms, ease-out.
  No bounce.

## Deliverables / checklist

- [x] `src/` app: HID++ module (ported, with the device-discovery part adapted to Windows),
      state/cache, hotkeys, tray, QML panel
- [ ] Verified on this machine with the real mouse: reads the channel, reads the names,
      switches away to the Linux machine (`2`), and the Linux side can send it back (`MEH + 1`;
      this machine turned out to be channel 1, `NB1MRUC1`). Reading channel and names: verified.
- [x] Hotkeys verified on the Slovak layout
- [x] Toasts appear and replace each other instead of stacking (if feasible)
- [x] Start-with-Windows toggle works
- [x] `build.ps1` (or similar) producing `dist\MarekovEasyMxMasterSwitcher.exe` via PyInstaller
- [x] Optional: GitHub Actions workflow (`windows-latest`) building the exe and attaching it to a
      release on tag push
- [x] README updated: install/run, build, Logi Options+ notes, known limitations, screenshot of
      the Windows panel; mark this TODO done

## Out of scope

- macOS.
- Other Logitech devices. Keep the product ID in one constant, though, so others could be added.
- Changing anything in the reference Linux files. They live in the user's dotfiles repo; the copies
  here are for reference only.
