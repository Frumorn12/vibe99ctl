# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
