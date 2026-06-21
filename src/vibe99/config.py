"""Project-wide constants and tunable defaults.

Anything here that is not yet confirmed on hardware carries a ``# TO-VERIFY``
marker and a sensible default derived from sibling devices, so the tool runs
end-to-end in dry-run mode today and only needs a constant changed once the real
value is measured.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# HID report geometry
# --------------------------------------------------------------------------- #
# Most of these vendor keyboards expose a 64-byte output report on a
# vendor-defined usage page. The first byte is frequently a Report ID.
#
# TO-VERIFY: confirm report length and whether a numbered Report ID is used.
HID_REPORT_SIZE = 64
HID_REPORT_ID = 0x00  # 0x00 means "no numbered report"; many devices use this.

# Vendor usage page used to single out the control interface among the several
# HID interfaces a keyboard exposes (keyboard, consumer-control, vendor).
# 0xFF00 is the most common vendor-defined page.
# TO-VERIFY.
VENDOR_USAGE_PAGE = 0xFF00


@dataclass(frozen=True)
class ScreenSpec:
    """Geometry and pixel format of the integrated TFT screen.

    The Vibe99 has a 1.06" panel (confirmed from marketing material). The exact
    pixel resolution is *not* published; 240x240 RGB565 is the most common panel
    in this device class and is used as the default until measured.
    """

    width: int = 240  # TO-VERIFY (probable)
    height: int = 240  # TO-VERIFY (probable)
    # "rgb565-le" is by far the most common on SPI TFTs driven over HID.
    pixel_format: str = "rgb565-le"  # TO-VERIFY (probable)

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def bytes_per_pixel(self) -> int:
        return 2 if self.pixel_format.startswith("rgb565") else 3

    @property
    def frame_bytes(self) -> int:
        return self.pixel_count * self.bytes_per_pixel


# Default screen used everywhere unless overridden by the user/CLI.
DEFAULT_SCREEN = ScreenSpec()

# --------------------------------------------------------------------------- #
# Animation / media limits
# --------------------------------------------------------------------------- #
# USB Full-Speed HID sustains roughly 64 KB/s, so on-device animation is only a
# handful of fps. We cap conversion defaults to keep uploads sane.
DEFAULT_ANIMATION_FPS = 5  # TO-VERIFY (probable ceiling ~5-10 fps)
MAX_ANIMATION_FRAMES = 120  # safety cap to avoid multi-MB uploads

# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #
# Small inter-report delay (seconds) when streaming many chunks, to avoid
# overrunning the device's receive buffer during a large screen upload.
INTER_CHUNK_DELAY_S = 0.002  # TO-VERIFY (tune against real hardware)
READ_TIMEOUT_MS = 1000
