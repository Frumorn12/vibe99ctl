# Vibe99 protocol notes

> **Status: DRAFT / UNVERIFIED.** Nothing here is confirmed on real Vibe99
> hardware yet. This document is the single source of truth the code is built
> against — when you confirm a field, update both this file and the matching
> constant in `src/vibe99/config.py` / `src/vibe99/protocol/`.

Legend: ✅ confirmed · 🟡 probable · ❓ to verify

## 1. Transport

| Item | Value | Conf. | Source |
|---|---|---|---|
| Bus | USB HID | 🟡 | Device class; siblings use HID |
| Connection for config | Wired (USB-C) | ✅ | Mechlands driver page / reviews |
| Report size | 64 bytes | ❓ | Common default for the OEM family |
| Numbered Report ID | `0x00` (none) | ❓ | Common default |
| Control interface | Vendor usage page `0xFF00` | ❓ | Common default |

A keyboard exposes several HID interfaces (boot keyboard, NKRO, consumer
control, vendor). Commands go to the **vendor** interface. Identify it by its
usage page (`>= 0xFF00`) — see `vibe99 list-devices --all`.

## 2. USB identity

| VID | PID | Meaning | Conf. |
|---|---|---|---|
| `0x3151` | `0x4011` | Vibe99 / OEM sibling | 🟡 |
| `0x3151` | `0x4015` | sibling | 🟡 |
| `0x3151` | `0x4010` | wired control (placeholder) | ❓ |

> These are seeded from the `controlhub.top` / `qmk.top` WebHID device family
> (e.g. AttackShark K86). **Confirm with `vibe99 list-devices --all` on a real
> Vibe99 and open an issue.**

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

## 5. Screen (🟡 structure, ❓ bytes)

- Panel: 1.06" TFT ✅. Resolution **240×240 RGB565 little-endian** 🟡/❓.
- Frame size at 240×240 RGB565 = `240*240*2` = **115 200 bytes**.
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
