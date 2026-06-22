"""Project-wide constants and tunable defaults.

Anything here that is not yet confirmed on hardware carries a ``# TO-VERIFY``
marker and a sensible default derived from sibling devices, so the tool runs
end-to-end in dry-run mode today and only needs a constant changed once the real
value is measured.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# HID report geometry  (CONFIRMED from the real Vibe99 report descriptors)
# --------------------------------------------------------------------------- #
# The wired Vibe99 (VID:PID 05ac:024f, "SONiX Mechlands Vibe99") exposes TWO
# vendor interfaces, decoded from /sys/.../report_descriptor:
#
#   * Control channel  — usage page 0xFF13, usage 0x01:
#       64-byte Input + 64-byte Output + 64-byte Feature, NO numbered Report ID.
#       This carries commands (RGB, clock, settings).  ✅
#   * Screen channel   — usage page 0xFF68, usage 0x61:
#       64-byte Input + **4096-byte Output**, NO numbered Report ID.
#       The big output report is the image/pixel pipe.  ✅
#
# In 2.4G wireless mode the vendor pages differ (0xFF60, smaller reports), which
# is why the official tool requires WIRED mode to configure.  ✅
HID_REPORT_SIZE = 64  # control channel output/feature report  ✅
SCREEN_REPORT_SIZE = 4096  # screen channel output report  ✅
HID_REPORT_ID = 0x00  # no numbered Report ID on either vendor interface  ✅

# Usage pages used to single out the right interface among the keyboard's many
# HID interfaces (boot keyboard, consumer control, mouse, vendor x2).
CONTROL_USAGE_PAGE = 0xFF13  # ✅ commands (RGB / clock / settings)
SCREEN_USAGE_PAGE = 0xFF68  # ✅ image/pixel upload
# Wireless (2.4G) vendor page, for reference / future support.
WIRELESS_USAGE_PAGE = 0xFF60  # ✅ (config still recommended over wired)

# Backwards-compatible alias: "the" vendor control page.
VENDOR_USAGE_PAGE = CONTROL_USAGE_PAGE


@dataclass(frozen=True)
class ScreenSpec:
    """Geometry and pixel format of the integrated TFT screen.

    The Vibe99 has a 1.06" panel (confirmed from marketing material). The exact
    pixel resolution is *not* published; 240x240 RGB565 is the most common panel
    in this device class and is used as the default until measured.
    """

    width: int = 96  # ✅
    height: int = 160  # ✅
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
INTER_CHUNK_DELAY_S = 0.035  # Match official driver cmd_delaytime value=35
READ_TIMEOUT_MS = 1000
