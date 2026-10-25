# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Screen works on real hardware
- **Fixed the screen upload** (images, GIFs, videos), verified on a wired
  Vibe99: upload command byte 2 is `gif_count` = 1 (not a 2/3 "mode"), the data
  is `0xFF`-padded, and the host now **waits for the keyboard's per-chunk ACK**
  (`01 5a 02`) on the screen interface instead of firing chunks blindly.
- Linux: use hidapi's **hidraw** backend. The libusb backend could not see the
  product string / usage pages under the `apple` driver and bypassed the udev
  rule.
- Screen geometry and limits confirmed from the official driver config:
  96×160 RGB565 LE, up to 255 frames, delays in 2 ms units.
- GIFs keep their own per-frame timing (subsampling merges delays).
- Videos: decoded by ffmpeg, streamed, sampled at `--fps` from `--start` for
  `--max-frames` frames. Previously the whole video was decoded into memory and
  120 frames were spread over its full length.
- Fast RGB565 conversion with numpy when available.
- Upload progress bar and missing-ACK warning in the CLI; dry-run no longer
  dumps every data chunk.

### Lights work on real hardware
- **Fixed the RGB packet**: `[0] effect [1..3] RGB [8] rainbow [9] brightness
  [10] speed [11] direction [14..15] AA 55` (there was a spurious byte before
  RGB), followed by `04 02` and `04 F0`; no readback for the payload and apply
  packets (new `Packet.readback`). Verified with static green.
- The 20 real effects from the official driver (0 off … 11 Rolling = factory
  default … 19 Shuttle), all usable by name in `vibe99 rgb preset`; old preset
  names kept as aliases. New `--reverse` for direction.

### Added
- **`vibe99 gui`**: desktop app with three pages: *Schermo* (local library,
  online GIF/sticker store via Tenor search, live screen-size preview,
  one-click upload), *Luci* (effects, colors, brightness, speed, direction,
  applied live) and *Tastiera* (clock sync, auto-sync on plug-in, stock
  animation, status). Follows the Omarchy theme colors.
- `data/70-vibe99.rules` (udev), `data/vibe99.desktop`, `data/vibe99.svg`.
- Tests for the runner ACK handling, GIF timing, video sampling and RGB layout.

### Fixed
- Ruff lint errors left by the previous commit (CI).

### Added / Changed
- **Confirmed USB identity & transport from real hardware** (report descriptors):
  device is `05ac:024f` (SONiX, reuses Apple's VID:PID — now disambiguated by
  product string). Control interface = usage page `0xFF13` (64-byte reports),
  screen interface = usage page `0xFF68` (**4096-byte** output report).
- Screen pipeline now streams ~4 KB chunks (a 240×240 frame is ~31 reports,
  down from ~2060).
- Discovery selects the control interface by usage page and can locate the
  screen interface; catalog requires the "Vibe99" product string.
- Dropped Python 3.9 (EOL); minimum is now **3.10** (fixes runtime evaluation of
  PEP 604 unions in Typer).
- Documented the captured report descriptors in `docs/protocol.md` (Appendix A).

## [0.1.0] - 2026-06-21

### Added
- Initial project scaffolding: packaging, CI, docs, tests.
- Device discovery layer with a curated (and explicitly *unverified*) VID/PID table.
- HID transport abstraction with a safe **dry-run** mode that never writes to hardware.
- Generic, pluggable packet-framing layer (`opcode`, `payload`, checksum helpers)
  designed to be filled in as the protocol is reverse-engineered.
- RGB command builders (single color, per-effect presets) — encoding marked *to-verify*.
- Screen pipeline: Pillow-based image → RGB565 conversion and HID chunking.
- Media pipeline: GIF/video → frame sequence conversion (video is **converted**, not
  streamed — the device has no native video support).
- Clock sync command builder.
- Typer-based CLI: `info`, `list-devices`, `rgb`, `screen`, `clock`, `dump-descriptor`,
  `protocol`, `doctor`.
- Reverse-engineering documentation and protocol notes.

### Known limitations
- The wire protocol is **not yet confirmed on real hardware**. All command encoders are
  implemented against a best-effort model and gated behind dry-run by default.
- See `docs/assumptions-and-limits.md` for the confirmed / probable / to-verify matrix.

[Unreleased]: https://github.com/Frumorn12/vibe99ctl/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Frumorn12/vibe99ctl/releases/tag/v0.1.0
