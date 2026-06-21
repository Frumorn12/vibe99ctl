# Reverse-engineering guide

This document explains how to responsibly capture the Vibe99 protocol so we can
turn the 🟡/❓ entries in [`protocol.md`](protocol.md) into ✅.

> **Legal & ethical note.** This is interoperability research on hardware *you
> own*. Don't redistribute the vendor's binaries or assets. Capture only your own
> traffic. The goal is a clean-room, byte-level description — not copying code.

## The golden rule: one action per capture

Decoding is easy when only one thing changes. Set the keyboard to a known state,
start capturing, perform exactly **one** action (e.g. "set solid red"), stop.
Repeat for each parameter. Name your files accordingly (`rgb_red.txt`,
`rgb_green.txt`, `bright_50.txt`, `img_solid_red.bin`, ...).

## Path A — WebHID console hook (recommended, no special tools)

Many keyboards in this OEM family ship a **WebHID** web driver (look for a
"web driver" link, or try `controlhub.top` / `qmk.top`). WebHID is plain
JavaScript, so you can read every packet from Chrome/Edge DevTools.

1. Connect the keyboard in **wired** mode.
2. Open the web driver, open **DevTools → Console**.
3. Paste this hook **before** clicking anything in the UI:

   ```js
   (() => {
     const fmt = (d) => [...new Uint8Array(d.buffer ?? d)]
       .map(b => b.toString(16).padStart(2, '0')).join(' ');
     const tx = HIDDevice.prototype.sendReport;
     HIDDevice.prototype.sendReport = function (id, data) {
       console.log('TX id=' + id, fmt(data));
       return tx.call(this, id, data);
     };
     const feat = HIDDevice.prototype.sendFeatureReport;
     HIDDevice.prototype.sendFeatureReport = function (id, data) {
       console.log('FEAT id=' + id, fmt(data));
       return feat.call(this, id, data);
     };
     navigator.hid.addEventListener('connect', e =>
       console.log('connect', e.device.vendorId.toString(16), e.device.productId.toString(16)));
     console.log('hook installed');
   })();
   ```

4. Click the device to grant access; note the logged `vendorId`/`productId`.
5. Perform **one** action; copy the `TX`/`FEAT` lines.
6. (Optional) Save the loaded JS for offline reading: DevTools → Sources →
   right-click the driver JS → *Save as*. The encoder functions there are the
   canonical truth.

## Path B — USB sniffing (Wireshark)

Use this when there's no web driver, or to cross-check Path A.

### Linux (usbmon)
```bash
sudo modprobe usbmon
# find the bus/device:
lsusb            # note Bus 00X Device 0YY: ID 3151:4011 ...
sudo wireshark   # capture interface "usbmonX" (X = bus number)
```
Wireshark display filter (replace device number):
```
usb.device_address == <YY> && usb.transfer_type == 0x01
```
`HID Data` lives in the URB payload of interrupt/control transfers.

### Windows (USBPcap)
Install [USBPcap](https://desowin.org/usbpcap/), select it in Wireshark, run the
official driver, perform one action, stop.

### Tip
You can also cross-reference against [OpenRGB](https://openrgb.org/) packet
captures for similar keyboards to gain confidence in opcode/checksum guesses.

## Decoding workflow

For each captured action:

1. **Find the report length & Report ID** (first byte). Update
   `HID_REPORT_SIZE` / `HID_REPORT_ID`.
2. **Find the opcode** — the byte that's constant within a command family but
   differs between families (RGB vs screen vs clock).
3. **Diff one-parameter changes.** Compare `rgb_red` vs `rgb_green`: the bytes
   that differ are the R/G/B fields. Compare `bright_50` vs `bright_100` for the
   brightness field, etc.
4. **Find the checksum.** Take all bytes except the last 1–2 and run:
   ```bash
   vibe99 protocol checksum "06 01 64 ff 00 00"
   ```
   Match the output against the trailing byte(s). Try over different byte ranges
   (with/without report id, with/without padding).
5. **Screen uploads:** look at the first packet (`BEGIN`: should contain width,
   height, total size), the repeated `DATA` packets (chunk index increments),
   and a final `END`. Confirm pixel order by uploading a known image (e.g. a
   single red pixel top-left) and checking what shows.

## Recording your findings

- Update [`protocol.md`](protocol.md): flip 🟡/❓ → ✅ and cite the capture.
- Update the code constant/enum and add a test in `tests/`.
- Open a PR, or an issue using the **protocol capture** template. Attach the
  scrubbed capture. Store raw captures under `captures/` (gitignored by default).

## Safety while testing writes

- Use `--apply` only once you have a plausible encoding; otherwise stay in
  dry-run and inspect the hex.
- Start with low-risk commands (clock sync, brightness) before screen uploads.
- Keep the official driver handy to restore a known-good state.
