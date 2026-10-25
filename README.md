# vibe99ctl

**An open-source terminal driver for the Mechlands Vibe99 keyboard — control RGB, the integrated TFT screen, and the clock from your shell. No proprietary GUI required.**

[![CI](https://github.com/Frumorn12/vibe99ctl/actions/workflows/ci.yml/badge.svg)](https://github.com/Frumorn12/vibe99ctl/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

---

> **Status.** The **screen works on real hardware**: static images, GIFs and
> videos (converted to an on-device animation), verified on a wired Vibe99. The
> protocol (`04 18` → `04 72` → 4 KB chunks, each ACKed → `04 02`) and the
> screen geometry (96×160 RGB565) are confirmed; see
> [`docs/protocol.md`](docs/protocol.md). **RGB lighting** (20 built-in effects,
> color/rainbow, brightness, speed, direction) is verified too, and the clock
> sync is accepted by the keyboard. In the CLI, write commands still run in
> **dry-run** by default and only send with `--apply`.

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
| Desktop app: screen gallery + GIF store, lights, clock | `vibe99 gui` | 🟢 works today |
| Screen: static image | `vibe99 screen upload-image` | 🟢 verified on hardware |
| Screen: animation (GIF) | `vibe99 screen upload-animation` | 🟢 verified (keeps GIF timing) |
| Screen: video → animation | `vibe99 screen upload-video` | 🟢 **converts** (no native video) |
| Clock sync | `vibe99 clock sync` | 🟡 accepted by the keyboard |
| RGB: solid color | `vibe99 rgb set` | 🟢 verified on hardware |
| RGB: 20 effects, rainbow/color, speed, direction | `vibe99 rgb preset` | 🟢 verified |
| RGB: brightness / off | `vibe99 rgb brightness` / `off` | 🟢 same encoder |
| Device discovery | `vibe99 list-devices` / `info` | 🟢 works today |
| Diagnostics | `vibe99 doctor` | 🟢 works today |
| RE helpers | `vibe99 protocol ...` / `dump-descriptor` | 🟢 works today |

🟢 = verified on a real Vibe99 · 🟡 = implemented, effect not yet verified

### About "video" support — read this

The Vibe99 **does not play real video**. It stores **up to 255 frames** in
flash, each with its own delay (2 ms steps), and loops them smoothly. So
`vibe99 screen upload-video` takes a stretch of your video (`--start`, `--fps`,
`--max-frames`; default 100 frames at 15 fps ≈ 6.5 s), fits it to the 96×160
screen and uploads it as an animation.

Uploading is the slow part: the keyboard is USB Full-Speed and writes every
4 KB chunk to flash before acknowledging it, so it takes **~1.1 s per frame**
(100 frames ≈ 2 minutes). The keyboard keeps working while it uploads.

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
pip install -e ".[gui]"          # the gallery (PyQt6); or use your distro's PyQt6
```

On Linux, let your user talk to the keyboard without root (the rule only
matches devices whose product name contains "Vibe99", so a real Apple keyboard
with the same ID is left alone):

```bash
sudo install -m 644 data/70-vibe99.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=hidraw
```

Optional desktop launcher: copy `data/vibe99.desktop` to
`~/.local/share/applications/` and `data/vibe99.svg` to
`~/.local/share/icons/hicolor/scalable/apps/`.

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

## Gallery (GUI)

```bash
vibe99 gui
```

A desktop app with three pages:

**Schermo** — two tabs and a live preview:

- **Libreria** — your GIFs and videos (`~/.local/share/vibe99/libreria`). Add
  files, open the folder, delete.
- **Store** — search GIFs and transparent stickers online (Tenor) by keyword,
  with one-click suggestions. Anything you upload is saved to the library.
- **Preview** — shows the exact frames that will be uploaded at screen size,
  with framing (fit/crop/stretch), frame cap, and for videos the speed and
  start time, plus an upload-time estimate. *Metti sulla tastiera* uploads with
  a progress bar.

**Luci** — the 20 built-in effects (named as in the official driver), rainbow or
one of the color swatches / any color, brightness and speed sliders (0-5) and
direction. Changes are applied to the keyboard live and remembered.

**Tastiera** — clock sync (also automatic when you plug the keyboard in while
the app is open), restore the stock Mechlands animation, connection status.

The window follows the current Omarchy theme colors when available.

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
Install the udev rule from [Installation](#installation) (`data/70-vibe99.rules`)
and re-plug the keyboard.

> Note: on Linux vibe99ctl uses hidapi's **hidraw** backend (the `hidraw`
> module bundled with the `hidapi` wheel). The default libusb backend can't see
> the product string or usage pages while the kernel's `apple` driver owns the
> keyboard, and needs raw USB access.

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
- **Confirmed** — on hardware and in the official driver's config: screen is
  **96×160 RGB565 little-endian**, row-major; animations hold up to **255
  frames** with per-frame delays; the full screen upload sequence and its
  per-chunk ACK (see [`docs/protocol.md`](docs/protocol.md)).
- **Confirmed** — RGB lighting packet and effect list (see
  [`docs/protocol.md`](docs/protocol.md)).
- **To verify**: the exact clock byte layout (accepted and echoed by the
  keyboard).

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
