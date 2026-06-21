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

## ✅ Confirmed — from the real device's HID report descriptors

- USB identity is **`05ac:024f`**, manufacturer **SONiX**, product
  **"SONiX Mechlands Vibe99"** (wired) / **"2.4G Wireless Receiver"** (dongle).
  It **reuses Apple's VID:PID**, so matching also requires the product string.
- Two wired vendor interfaces, **no numbered Report ID**:
  - **Control** — usage page `0xFF13`, usage `0x01`: 64-byte Input/Output/Feature.
  - **Screen** — usage page `0xFF68`, usage `0x61`: 64-byte Input + **4096-byte
    Output** (the pixel pipe).
- 2.4G mode uses different, smaller vendor reports (`0xFF60`) → config over wired.
- The chip is **SONiX**, consistent with this OEM keyboard family.

## 🟡 Probable

- The screen is **RGB565**, most likely **240×240** (dominant panel in this class).
- Image upload is **chunked** over the 4096-byte screen report in a
  BEGIN/DATA/END flow.
- On-device animation runs at only **a few fps** due to USB bandwidth.
- A WebHID web driver likely exists for this OEM family (makes RE far easier).

## ❓ To verify on real hardware

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
