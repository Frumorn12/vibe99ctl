# vibe99ctl

**An open-source terminal driver for the Mechlands Vibe99 keyboard — control RGB, the integrated TFT screen, and the clock from your shell. No proprietary GUI required.**

[![CI](https://github.com/Frumorn12/vibe99ctl/actions/workflows/ci.yml/badge.svg)](https://github.com/Frumorn12/vibe99ctl/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

---

> ⚠️ **Honest status up front.** The Vibe99 wire protocol is **not officially
> documented** and is **not yet confirmed on real hardware**. This project ships
> a complete, well-tested architecture and a *best-effort* protocol model derived
> from sibling devices in the same OEM family. **Write commands run in dry-run by
> default** and only send to the keyboard when you pass `--apply`. See
> [Assumptions & limits](#assumptions--limits) and
> [`docs/assumptions-and-limits.md`](docs/assumptions-and-limits.md).

## Overview

The Mechlands Vibe99 is a 96%/1800-layout wireless mechanical keyboard with a
**1.06" TFT screen**. Its official driver is a **Windows-only GUI** that requires
a **wired** connection to configure RGB lighting, upload images/GIFs to the
screen, and sync the clock.

`vibe99ctl` aims to do all of that from the terminal, on **Linux first** and
**Windows** too, with a clean, scriptable CLI.

### What it does

| Feature | Command | Status |
|---|---|---|
| RGB: solid color | `vibe99 rgb set` | 🟡 encoder built, protocol to verify |
| RGB: effects/presets | `vibe99 rgb preset` | 🟡 encoder built, protocol to verify |
| RGB: brightness / off | `vibe99 rgb brightness` / `off` | 🟡 encoder built |
| Screen: static image | `vibe99 screen upload-image` | 🟡 pipeline built, protocol to verify |
| Screen: animation (GIF) | `vibe99 screen upload-animation` | 🟡 pipeline built |
| Screen: video → animation | `vibe99 screen upload-video` | 🟡 **converts** (no native video) |
| Clock sync | `vibe99 clock sync` | 🟡 encoder built |
| Device discovery | `vibe99 list-devices` / `info` | 🟢 works today |
| Diagnostics | `vibe99 doctor` | 🟢 works today |
| RE helpers | `vibe99 protocol ...` / `dump-descriptor` | 🟢 works today |

🟢 = works now · 🟡 = implemented, needs a hardware capture to confirm the bytes

### About "video" support — read this

The Vibe99 **does not play real video**. Its firmware accepts still images and
**GIF/animation frames**. `vibe99 screen upload-video` therefore **converts** a
video into a short, low-fps frame sequence and uploads it as an animation. The
result is intentionally choppy — that's a hardware limitation, not a bug, and we
refuse to pretend otherwise.

## Installation

```bash
# From source (recommended while in alpha)
git clone https://github.com/Frumorn12/vibe99ctl.git
cd vibe99ctl
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# Optional: enable real video conversion (mp4/webm/...). GIFs work without this.
pip install -e ".[media]"        # imageio + ffmpeg
pip install -e ".[media-full]"   # + OpenCV
```

### Requirements

**Linux**
- Python 3.10+
- `hidapi` system libs: `sudo apt install libhidapi-hidraw0` (Debian/Ubuntu) or
  the build headers `libudev-dev libusb-1.0-0-dev` if compiling the wheel.
- A udev rule for non-root access (see [Troubleshooting](#troubleshooting)).

**Windows**
- Python 3.10+
- The `hidapi` wheel bundles the DLL; no extra driver needed for HID access.
- Put the keyboard in **wired** mode to configure it (same as the official tool).

## Usage

> Remember: write commands are **dry-run by default**. Add `--apply` to actually
> send bytes to the keyboard.

```bash
# Discover hardware
vibe99 info
vibe99 list-devices            # only known/candidate devices
vibe99 list-devices --all      # every HID interface (use this to find your VID/PID)
vibe99 doctor                  # environment & connectivity checks

# RGB
vibe99 rgb set "#ff8800"                 # dry-run preview
vibe99 rgb set red --brightness 60 --apply
vibe99 rgb preset rainbow --speed 80 --apply
vibe99 rgb preset breathing --color "0,128,255" --apply
vibe99 rgb brightness 40 --apply
vibe99 rgb off --apply

# Screen
vibe99 screen upload-image logo.png --fit cover --apply
vibe99 screen upload-animation cat.gif --fps 5 --apply
vibe99 screen upload-video clip.mp4 --max-frames 60 --apply   # converted, not streamed

# Clock
vibe99 clock sync --apply
vibe99 clock sync --at 2026-12-31T23:59:00 --apply

# Reverse-engineering helpers
vibe99 dump-descriptor --all
vibe99 protocol sniff-notes
vibe99 protocol checksum "06 01 64 ff"
vibe99 protocol ping --apply
```

Targeting a specific device (e.g. when auto-detection is wrong):

```bash
vibe99 --vid 0x05ac --pid 0x024f rgb set blue --apply
vibe99 --path "/dev/hidraw3" info
```

See [`examples/`](examples/) for copy-paste recipes.

## Examples (CLI)

```bash
# A red "breathing" mood light at half brightness
vibe99 rgb preset breathing --color red --brightness 50 --apply

# Put your logo on the screen, cropped to fill
vibe99 screen upload-image ~/Pictures/logo.png --fit cover --apply

# Loop a GIF at ~5 fps
vibe99 screen upload-animation ~/Pictures/loading.gif --fps 5 --apply

# Keep the on-screen clock correct (e.g. from cron / a login hook)
vibe99 clock sync --apply
```

## Troubleshooting

**`No Mechlands Vibe99 (or compatible) device found`**
- Connect the keyboard with the **USB-C cable** (wired mode) — wireless/2.4G may
  enumerate under a different PID or not expose the control interface.
- Run `vibe99 list-devices --all` and look for the vendor interface (marked `*`).
  Found it? Pass `--vid/--pid` explicitly and please
  [open a protocol issue](.github/ISSUE_TEMPLATE/protocol_capture.md).

**Linux: `open failed / access denied`**
Create a udev rule (replace the IDs with yours from `list-devices --all`):

```bash
sudo tee /etc/udev/rules.d/99-vibe99.rules >/dev/null <<'EOF'
# Mechlands Vibe99 (SONiX) — shares Apple's 05ac:024f, so this rule also
# loosens permissions on Apple keyboards with that ID. Adjust if that matters.
KERNEL=="hidraw*", ATTRS{idVendor}=="05ac", ATTRS{idProduct}=="024f", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05ac", ATTRS{idProduct}=="024f", MODE="0660", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```
Then re-plug the keyboard.

> Note: on Linux the kernel binds this keyboard to the `apple` HID driver and
> `hidapi` may report `usage_page = 0` for its interfaces, so interface
> auto-selection by usage page works best on Windows. You can always pin an
> interface with `--path` (find it via `vibe99 list-devices --all`).

**`hidapi` import fails**
Install the system lib (`libhidapi-hidraw0`) or the build headers, then
`pip install --force-reinstall hidapi`. Run `vibe99 doctor` to confirm.

**It "sent" but nothing changed**
You probably ran without `--apply` (dry-run), or the opcode/checksum guess is
wrong for your firmware. The latter is expected until the protocol is confirmed —
capturing it is exactly how you can help (see below).

## Reverse engineering notes

The fastest path to confirming the protocol is the **WebHID** web driver that
this OEM family ships: it's plain JavaScript, so you can hook
`HIDDevice.prototype.sendReport` in Chrome DevTools and read every packet. A USB
sniff (Wireshark + usbmon/USBPcap) is the fallback. Full, step-by-step guidance:

- [`docs/reverse-engineering.md`](docs/reverse-engineering.md) — how to capture.
- [`docs/protocol.md`](docs/protocol.md) — the byte-level spec (fill as we learn).
- `vibe99 protocol sniff-notes` — the short version, in your terminal.

If you own a Vibe99, a single clean capture of one action (e.g. "set red") is
hugely valuable — please share it via the protocol issue template.

## Feature status

See the live matrix in [Overview](#what-it-does) and the detailed breakdown in
[`docs/assumptions-and-limits.md`](docs/assumptions-and-limits.md).

## Assumptions & limits

- **Confirmed** — official/marketing: 1.06" TFT; shows
  date/time/battery/connection/lock indicators; supports GIFs and animations
  built from JPG/PNG with text; configured over a **wired** connection; official
  driver is Windows-only.
- **Confirmed** — from the real device's HID report descriptors:
  - USB identity **`05ac:024f`**, manufacturer **SONiX**, product
    **"Mechlands Vibe99"** (it reuses Apple's VID:PID, so we also match the
    product string to avoid touching real Apple keyboards).
  - Two vendor interfaces: **control** = usage page `0xFF13` (64-byte
    out/feature reports), **screen** = usage page `0xFF68` (**4096-byte** output
    report for pixel data). No numbered Report ID.
  - 2.4G mode exposes different, smaller vendor reports (`0xFF60`) — hence
    config is done wired.
- **Probable**: screen is RGB565, likely 240×240; on-device animation runs at
  only a few fps due to USB Full-Speed bandwidth.
- **To verify on real hardware**: the command opcodes, payload layouts and
  checksum algorithm for RGB / screen / clock (needs a capture of the Windows or
  WebHID driver's traffic), plus exact screen resolution and pixel order.

Everything "probable"/"to verify" is centralised in `config.py` and the
`protocol/` encoders, each marked with `# TO-VERIFY`, so confirming the protocol
is a matter of editing a few constants — not rewriting the tool.

## Contributing

Captures, fixes and Vibe99 hardware testing are all welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer & safety

This is an **unofficial** project. It is **not affiliated with, endorsed by, or
supported by Mechlands**. "Mechlands" and "Vibe99" are trademarks of their
respective owners; they are used here only to describe compatibility.

Writing unverified data to a USB device carries some risk. This tool mitigates it
by defaulting to dry-run, but **you use it at your own risk**. The authors accept
no liability for any damage to your hardware (see the [LICENSE](LICENSE)). All
reverse engineering here is for **interoperability** with hardware you own.

## License

[MIT](LICENSE) © 2026 Andrea Brescia
