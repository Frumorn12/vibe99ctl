"""vibe99ctl — an open-source terminal driver for the Mechlands Vibe99 keyboard.

This package controls the keyboard's RGB lighting, its integrated 1.06" TFT
screen, and its on-board clock over USB HID, without the proprietary GUI driver.

IMPORTANT: the Vibe99 wire protocol is not officially documented. Command
encoders in this package are built from a best-effort model and from captures of
sibling devices that share the same OEM web driver. Everything that has not been
verified on real hardware is clearly marked and gated behind a *dry-run* default.
See ``docs/assumptions-and-limits.md``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
