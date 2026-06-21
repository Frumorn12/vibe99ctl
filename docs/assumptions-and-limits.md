# Assumptions & limits

This project is honest about what it knows. Below, every relevant fact is filed
under **Confirmed**, **Probable**, or **To verify**.

## ✅ Confirmed (official / marketing / reviews)

- The Vibe99 has a **1.06" TFT screen**.
- The screen displays date, time, battery level, connection indicators, and
  Caps/Num/Win-Lock indicators.
- The screen supports **GIF animations** and **animations built from JPG/PNG**,
  with optional custom **text** overlays.
- There is **no native video** format — content is images/GIF frames.
- The official driver is **Windows-only** and requires the keyboard to be in
  **wired** mode to configure.
- The Vibe99 driver is essentially the same app as the Vibe75.

Sources: Mechlands product & driver pages; independent reviews (Root-Nation,
WCCFTech, EnostTech, GizmoVue).

## 🟡 Probable (inferred from OEM-sibling devices & common practice)

- USB **VID/PID** is in the `0x3151:0x40xx` family (from the
  `controlhub.top`/`qmk.top` WebHID device family, e.g. AttackShark K86).
- The control channel is a **vendor-defined HID interface** (usage page
  `0xFF00`), separate from the keyboard interface.
- HID reports are **64 bytes**.
- The screen is **RGB565**, most likely **240×240** (the dominant panel in this
  device class).
- Image upload is **chunked** over the 64-byte report in a BEGIN/DATA/END flow.
- On-device animation runs at only **a few fps** because USB Full-Speed HID
  sustains ~64 KB/s and a 240×240 RGB565 frame is ~115 KB.
- A WebHID web driver likely exists for this OEM family (makes RE far easier).

## ❓ To verify on real hardware

- Exact **VID/PID** of the Vibe99 (and whether wired vs 2.4G differ).
- Whether a **numbered Report ID** is used, and the exact report length.
- The exact **vendor usage page** / interface number of the control channel.
- The **opcode** values for RGB, screen, clock, device-info.
- The **checksum** algorithm (sum8 / xor / crc16 / none) and the byte range it
  covers.
- Exact **screen resolution** and **pixel byte order** (LE vs BE).
- The RGB **payload layout** (effect/brightness/speed/direction ordering, effect
  IDs).
- The **clock** byte layout (raw vs BCD, weekday convention, presence of a
  command to also set 12/24h or display mode).
- Whether animations are **stored on-device** or **host-driven**, and the max
  frame count / fps the firmware accepts.

## How this maps to the code

| Concern | Where | What to change when confirmed |
|---|---|---|
| Report size / id / usage page | `config.py` | `HID_REPORT_SIZE`, `HID_REPORT_ID`, `VENDOR_USAGE_PAGE` |
| Screen geometry / format | `config.py` `ScreenSpec` | `width`, `height`, `pixel_format` |
| VID/PID & confidence | `device/descriptors.py` | entries + `confidence` |
| Frame layout & checksum | `protocol/packets.py` | `frame()`, `CHECKSUM` |
| Opcodes | `protocol/packets.py` `Opcode` | enum values |
| RGB payload | `protocol/rgb.py` | payload order, `RgbEffect` values |
| Screen flow | `protocol/screen.py` | BEGIN/DATA/END layout |
| Clock layout | `protocol/clock.py` | payload bytes |

Every guessed value carries a `# TO-VERIFY` comment in the source, so they're
greppable: `grep -rn "TO-VERIFY" src/`.
