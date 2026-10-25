# Vibe99 protocol notes

> **Status: PARTIALLY CONFIRMED.** The USB identity, the HID transport and the
> **screen** and **RGB** protocols are confirmed on a real device (sections 1,
> 2, 4, 5, 6). The clock message is accepted and echoed by the keyboard; its
> exact byte layout is not yet verified on screen. This document is the single source of truth the code is built
> against — when you confirm a field, update both this file and the matching
> constant in `src/vibe99/config.py` / `src/vibe99/protocol/`.

Legend: ✅ confirmed · 🟡 probable · ❓ to verify

## 1. Transport (CONFIRMED from real report descriptors)

| Item | Value | Conf. |
|---|---|---|
| Bus | USB HID | ✅ |
| Connection for config | Wired (USB-C) | ✅ |
| Manufacturer / chip | SONiX | ✅ |
| Numbered Report ID | none (`0x00`) on both vendor interfaces | ✅ |
| Control interface | usage page `0xFF13`, usage `0x01`, 64B in/out/feature | ✅ |
| Screen interface | usage page `0xFF68`, usage `0x61`, **4096B** output + 64B in | ✅ |
| 2.4G vendor interface | usage page `0xFF60` (smaller reports) | ✅ |

The keyboard exposes 4 wired interfaces: `input0` boot keyboard (`0x0501`),
`input1` consumer/mouse (`0x0C`), `input2` **screen** (`0xFF68`), `input3`
**control** (`0xFF13`). Commands go to `0xFF13`; pixel data to `0xFF68`.

> Linux note: the kernel binds this device to the `apple` driver and `hidapi`
> may report `usage_page = 0`, so usage-page auto-selection is most reliable on
> Windows. Use `--path` to pin an interface on Linux.

## 2. USB identity (CONFIRMED)

| VID | PID | Product string | Meaning | Conf. |
|---|---|---|---|---|
| `0x05AC` | `0x024F` | `SONiX Mechlands Vibe99` | wired keyboard | ✅ |
| `0x05AC` | `0x024F` | `2.4G Wireless Receiver` | 2.4G dongle | ✅ |

> ⚠️ The Vibe99 **reuses Apple's `05ac:024f`** (Aluminium Keyboard). Match on the
> **product string** ("Vibe99") as well, or you may talk to a real Apple
> keyboard. `descriptors.py` enforces this via `product_match`.

## 3. Frame model (current best guess)

```
offset  size  field
0       1     Report ID         (only on the wire if non-zero)
1       1     opcode            (command family)
2       1     sub / seq         (sub-command or chunk index)
3       1     payload length    (meaningful bytes that follow)
4..     N     payload
last    1     checksum          (algorithm TBD: sum8 / xor / crc16)
        ...   zero padding to 64 bytes
```

Implemented in `protocol/packets.py:frame`. If captures disagree, change that
one function.

### Candidate opcodes (placeholders ❓)

| Name | Value | Notes |
|---|---|---|
| DEVICE_INFO | `0x01` | request firmware / status |
| RGB | `0x06` | lighting |
| SCREEN_BEGIN | `0x10` | announce frame transfer |
| SCREEN_DATA | `0x11` | pixel chunk |
| SCREEN_END | `0x12` | commit/display |
| SCREEN_MODE | `0x13` | mode / animation header |
| CLOCK_SYNC | `0x20` | date/time |

## 4. RGB lighting (✅ verified on hardware)

Same layout as the Ajazz AK820 Pro (same SONiX vendor driver family); verified
by setting static green on a real Vibe99.

| Step | Bytes | Readback |
|---|---|---|
| 1 | `04 18 00 …` | yes |
| 2 | `04 13 00 00 00 00 00 00 01 …` (one lighting packet follows) | yes |
| 3 | lighting packet (below) | **no** |
| 4 | `04 02 00 …` | yes |
| 5 | `04 F0 00 …` | **no** |

Lighting packet (64 bytes, no Report ID):

```
[0] effect   [1] R  [2] G  [3] B   [8] rainbow (1 = ignore RGB)
[9] brightness 0-5   [10] speed 0-5   [11] direction 0/1   [14] AA  [15] 55
```

Effects (official driver `1033.lan` 521-540): 0 LED Off, 1 Static, 2 SingleOn,
3 SingleOff, 4 Glittering, 5 Falling, 6 Colourful, 7 Breath, 8 Spectrum,
9 Outward, 10 Scrolling, 11 Rolling, 12 Rotating, 13 Explode, 14 Launch,
15 Ripples, 16 Flowing, 17 Pulsating, 18 Tilt, 19 Shuttle. Factory default:
`<light default_mode="11" default_brightness="5" default_speed="3"/>`.

## 5. Screen (✅ verified on hardware)

- Panel: 1.06" TFT, **96×160 portrait**, **RGB565 little-endian**, row-major,
  top-left first ✅ (official driver: `<screen width="96" height="160"/>`;
  confirmed with a test pattern on a real keyboard).
- One frame = `96*160*2` = **30 720 bytes**.

Upload sequence (control = `0xFF13` feature reports, screen = `0xFF68` output
reports; no numbered Report ID, so hidapi buffers start with `0x00`):

| Step | Interface | Bytes | Notes |
|---|---|---|---|
| 1 | control | `04 18 00 …` | start session; echoed back by GET_FEATURE |
| 2 | control | `04 72 01 00 00 00 00 00 <n lo> <n hi> …` | byte 2 = `gif_count` (1), bytes 8-9 = number of 4096-byte chunks |
| 3 | screen | n × 4096 bytes | after **each** chunk the keyboard sends a 64-byte input report `01 5a 02 00 …` once stored; wait for it (the official driver waits up to 300 ms) |
| 4 | control | `04 02 00 …` | commit |

Every control report is followed by a GET_FEATURE readback (the keyboard
echoes the command), with ~35 ms between reports (`cmd_delaytime` in the
driver's `rgb-keyboard.xml`).

The data stream is:

```
[256-byte header][frame 0][frame 1]...[0xFF padding to a multiple of 4096]
header[0]     = frame count (1..255)
header[1 + i] = delay of frame i, in 2 ms units (1..255); 0 for a static image
header[rest]  = 0xFF
```

### Bandwidth ✅
USB Full-Speed, 64-byte interrupt endpoints at 1 ms. Measured: **~0.147 s per
4 KB chunk** including the flash write, i.e. ~1.1 s per frame (841 chunks /
112 frames in 2 min 04 s).

## 6. Animation ✅

Animations are **stored on the keyboard** (header above, `gif_maxframes="255"`)
and loop on-device at the stored per-frame delays; playback is smooth. A static
image is a one-frame animation.

## 7. Clock sync (🟡 structure, ❓ bytes)

Payload (8 bytes): `[ century, year%100, month, day, hour, minute, second, weekday ]`
where weekday is `isoweekday() % 7` (0=Sun). BCD vs raw is ❓ — try raw first.

## 8. Checksum

Unknown ❓. Provided candidates: `sum8`, `xor8`, `crc16-ccitt`. Use
`vibe99 protocol checksum "<bytes>"` to match the last byte(s) of a real capture.

## How to confirm a field

1. Capture one isolated action (see `reverse-engineering.md`).
2. Identify opcode position, which byte changed, and the checksum.
3. Update this table (flip 🟡/❓ → ✅, cite the capture).
4. Update the matching constant/enum in code; add a regression test in `tests/`.
5. If a VID/PID is confirmed, set its `confidence="confirmed"` in `descriptors.py`.

## Appendix A — Captured HID report descriptors (wired Vibe99)

Read from `/sys/class/hidraw/hidrawN/device/report_descriptor` on Linux while a
real `SONiX Mechlands Vibe99` (`05ac:024f`) was connected by USB-C.

**input2 — SCREEN interface (usage page 0xFF68):**
```
06 68 ff 09 61 a1 01 09 62 15 00 26 ff 00 95 40 75 08 81 02
09 63 15 00 26 ff 00 96 00 10 75 08 91 02 c0
```
Decode: Usage Page 0xFF68, Usage 0x61, Collection(App); Input report = 64 bytes
(`95 40 75 08 81 02`); Output report = **4096 bytes** (`96 00 10 75 08 91 02`).

**input3 — CONTROL interface (usage page 0xFF13):**
```
06 13 ff 09 01 a1 01 15 00 26 ff 00 75 08 95 40 09 02 81 02
09 03 91 02 0a 00 ff b1 02 c0
```
Decode: Usage Page 0xFF13, Usage 0x01, Collection(App); 64-byte Input
(`09 02 81 02`), 64-byte Output (`09 03 91 02`), 64-byte Feature
(`0a 00 ff b1 02`). No Report ID.

**input0 — boot keyboard (0x0501)** and **input1 — consumer/mouse/keyboard +
vendor 0xFFFF report id 5** are the normal typing interfaces.

**2.4G receiver (`05ac:024f`, product "2.4G Wireless Receiver"):** vendor
interfaces use usage page **0xFF60** with 32-byte and 64-byte output reports —
smaller than wired, which is why configuration is done over USB-C.

### Still needed
The descriptors give us the *pipes* and their sizes, but not the *messages*.
To finish RGB / screen / clock we need a capture of the official driver's
traffic on these interfaces (WebHID `sendReport` hook or USBPcap on Windows).
See [reverse-engineering.md](reverse-engineering.md).
