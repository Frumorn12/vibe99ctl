# Contributing to vibe99ctl

Thanks for helping! The single most valuable contribution right now is a **clean
protocol capture from real Vibe99 hardware** — that's what turns this from a
solid skeleton into a fully working driver.

## Ways to help

1. **Protocol captures** (highest impact). See
   [`docs/reverse-engineering.md`](docs/reverse-engineering.md), then open an
   issue with the *protocol capture* template.
2. **Hardware testing** — try `--apply` commands and report what happened
   (`vibe99 doctor` output helps).
3. **Code** — fixes, new effects/presets, Windows polish, packaging.
4. **Docs** — clarity, troubleshooting, translations.

## Dev setup

```bash
git clone https://github.com/USERNAME/vibe99ctl.git
cd vibe99ctl
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # add ,media for video work: ".[dev,media]"
```

## Before you push

```bash
ruff check .          # lint
ruff format .         # format
pytest                # tests
```

CI runs the same on Linux + Windows across Python 3.9/3.11/3.12. Please keep it
green and add a test for any behaviour change.

## Code conventions

- Keep the layers separate: discovery / transport / protocol / media / cli.
  Command builders return `Packet`s; only `runner.py` and `transport.py` touch
  the wire.
- Anything not confirmed on hardware gets a `# TO-VERIFY` comment.
- New device IDs go in `device/descriptors.py` with an honest `confidence`.
- Don't add a dependency without a clear reason; heavy media deps stay optional.

## Confirming protocol details

When a capture confirms a field:
1. Update [`docs/protocol.md`](docs/protocol.md) (flip 🟡/❓ → ✅, cite the capture).
2. Update the constant/enum in code.
3. Add/adjust a test in `tests/`.
4. Bump the relevant status in the README table if a feature becomes 🟢.

## Reporting bugs

Use the bug template and include `vibe99 doctor` output, your exact command, OS,
and Python version.

## Code of conduct

Be kind and constructive. Assume good faith. This is a hobby/interoperability
project maintained in spare time.
