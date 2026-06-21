# Vibe99 protocol notes

> **Status: PARTIALLY CONFIRMED.** The USB identity and the HID transport
> (interfaces, usage pages, report sizes) are confirmed from a real device's
> report descriptors (see Appendix A). The **command messages** (RGB / screen /
> clock opcodes, payloads, checksum) are still a best-effort model pending a
> traffic capture. This document is the single source of truth the code is built
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

## 4. RGB lighting (🟡 structure, ❓ bytes)

Payload after the frame header:

```
[ effect, brightness(0-100), speed(0-100), R, G, B, direction ]
```

Effects (placeholder values): static=1, breathing=2, wave=3, rainbow=4,
ripple=5, reactive=6, off=0.

## 5. Screen (✅ transport, 🟡 structure, ❓ bytes)

- Panel: 1.06" TFT ✅. Resolution **240×240 RGB565 little-endian** 🟡/❓.
- Frame size at 240×240 RGB565 = `240*240*2` = **115 200 bytes**.
- Transport ✅: the screen interface (`0xFF68`) takes a **4096-byte output
  report**, so a frame is ~29 reports (not ~2000). No Report ID.
- Upload = `BEGIN` → many `DATA` chunks → `END`.

`BEGIN` payload (`<HHIB`): `width, height, total_bytes, frame_index`.
`DATA` payload: `<HH` (chunk_index, reserved) + pixel bytes.
`END` payload: `[frame_index]`.

### Bandwidth reality ✅(class) / ❓(exact)
USB Full-Speed HID ≈ 64 KB/s sustained → one 115 KB frame ≈ ~2 s; on-device
animation is only a few fps. This is why `upload-video` downsamples hard.

## 6. Animation (🟡)

`SCREEN_MODE` payload `<BB`: `frame_count, fps`, followed by each frame as a full
`BEGIN/DATA/END` group with incrementing `frame_index`. Whether the device
stores the animation on-board (documented for GIFs ✅) or needs host-driven
playback is ❓.

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
