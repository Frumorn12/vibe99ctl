---
name: Protocol capture / reverse-engineering report
about: Share a USB/HID capture or findings to help confirm the Vibe99 protocol
title: "[protocol] "
labels: ["protocol", "needs-hardware"]
---

## Hardware
- Keyboard variant / color:
- Firmware version (if shown on screen or in driver):
- Official driver version used for the capture:
- OS used for capture:

## Device identity
Output of `vibe99 list-devices --all` (or `lsusb -v` for the matching device):

```
<paste here>
```

## What action did you capture?
- [ ] RGB color/effect change
- [ ] Screen image upload
- [ ] Screen animation/GIF upload
- [ ] Clock / time sync
- [ ] Other:

## Capture
Attach the `.pcapng` (Wireshark/usbmon) or the WebHID `sendReport` log.
Please scrub anything sensitive. See `docs/reverse-engineering.md` for how to capture.

## Notes
Anything you already decoded (report IDs, opcodes, offsets, checksum guesses):
