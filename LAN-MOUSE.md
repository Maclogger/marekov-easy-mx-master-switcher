# Windows side of lan-mouse — do this first

**Priority changed:** the user now shares the mouse and keyboard over the network with
[lan-mouse](https://github.com/feschber/lan-mouse) instead of switching the mouse's Bluetooth channel.
The Linux side is already set up and running. Your job on this Windows laptop is the receiving side.
The tray app in `TODO.md` is **on hold**; don't build it unless the user asks again.

## Setup on the Linux side (already done)

- Machine: `MarekovArchLinux`, LAN IP **192.168.1.13** (Wi-Fi), lan-mouse **0.11.0**, UDP port **4242**.
- The Windows laptop is configured as the client to the **right** of the Linux monitors. When the
  cursor crosses the right edge, mouse and keyboard input goes to Windows. Pressing
  `A + S + D + F` together on the Linux keyboard pulls it back.
- Linux machine's certificate fingerprint (SHA-256):

  ```
  5c:0a:3c:54:f0:de:50:9e:9a:11:e2:6c:cf:7b:98:e7:e5:99:b8:47:37:73:d2:f2:9e:79:98:32:ef:3c:8d:7a
  ```

  Double-check it against what the Linux lan-mouse GUI shows under *General*. If they differ,
  trust the GUI and ask the user.

The Linux config and systemd unit are in `reference/linux/lan-mouse-config.toml` and
`reference/linux/lan-mouse.service`, for reference.

## Steps on Windows

1. **Install lan-mouse v0.11.0**: download `lan-mouse-windows-x86_64.zip` from
   https://github.com/feschber/lan-mouse/releases/tag/v0.11.0
   (`gh release download v0.11.0 -R feschber/lan-mouse -p lan-mouse-windows-x86_64.zip`), unpack
   it to e.g. `%LOCALAPPDATA%\Programs\lan-mouse\`. Stick to v0.11.0: the Linux side runs exactly
   that version, and the newer `main-*` pre-releases may speak a different protocol.
2. **Authorize the Linux machine:** in the lan-mouse GUI under *Incoming Connections*, authorize
   the fingerprint above (name it `MarekovArchLinux`). Then make it persistent in
   `%LOCALAPPDATA%`/`%APPDATA%`'s `lan-mouse\config.toml` (whichever lan-mouse actually uses; check),
   for example:

   ```toml
   port = 4242

   [authorized_fingerprints]
   "5c:0a:3c:54:f0:de:50:9e:9a:11:e2:6c:cf:7b:98:e7:e5:99:b8:47:37:73:d2:f2:9e:79:98:32:ef:3c:8d:7a" = "MarekovArchLinux"
   ```

   Optional, so the Windows touchpad can also reach Linux: add a client with `position = "left"`
   and `ips = ["192.168.1.13"]`. In that case, give the user the *Windows* fingerprint, because the
   Linux side then has to authorize it.
3. **Firewall:** allow inbound UDP 4242 on the *Private* profile only, e.g.
   `New-NetFirewallRule -DisplayName "lan-mouse" -Direction Inbound -Protocol UDP -LocalPort 4242 -Profile Private -Action Allow`.
   Make sure the home Wi-Fi network is set to *Private*, not *Public*.
4. **Autostart:** run lan-mouse in the background at login (Startup folder shortcut or Task
   Scheduler "At log on"; `lan-mouse daemon` if the GUI shouldn't open).
5. **Tell the user the Windows laptop's LAN IPv4** (`ipconfig`, the Wi-Fi adapter). The Linux config
   still has `ips = []` and needs it (`~/.config/lan-mouse/config.toml` in the dotfiles). Suggest a
   DHCP reservation on the router for both machines so the IPs don't change.
6. **Test with the user:** cursor across the right edge of the Linux screens → moves on Windows;
   typing on the Linux keyboard types on Windows; `A+S+D+F` returns.

## Known Windows limitations to tell the user about

- The cursor can be **invisible** on Windows if no physical mouse is attached there. The laptop's
  touchpad usually counts; if not, look for a workaround (e.g. the "show pointer" mouse-keys trick)
  and document it.
- Windows ignores injected input on the **lock screen / UAC secure desktop**, and in **elevated
  (admin) windows** unless lan-mouse itself runs elevated.
- No shared clipboard (lan-mouse doesn't have one).

## When you're done

- Write what you did (install path, config path, firewall rule, autostart method, anything that
  didn't match this doc) into a new section of `README.md` → *Windows lan-mouse setup*, and commit
  and push it to this repo. The user has allowed git here.
- Give the user, in your final message: the Windows LAN IP, and the Windows fingerprint if you
  set up the optional Windows → Linux direction. The Linux side then needs
  `ips = ["<that IP>"]` and `activate_on_startup = true` in `~/marekove-dotfiles/lan-mouse/.config/lan-mouse/config.toml`,
  then `systemctl --user restart lan-mouse`. The Linux agent will do that.
