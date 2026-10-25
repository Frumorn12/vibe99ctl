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

    The Vibe99 has a 1.06" panel, 96x160 portrait per the official driver's
    ``<screen width="96" height="160"/>``, fed row-major RGB565 little-endian
    (verified on hardware with a test pattern: colors and orientation correct).
    """

    width: int = 96  # ✅
    height: int = 160  # ✅
    pixel_format: str = "rgb565-le"  # ✅

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
# From the official driver's rgb-keyboard.xml:
#   <screen gif_headlength="256" gif_maxframes="255" gif_count="1" .../>  ✅
# The animation is stored on the keyboard: a 256-byte header (frame count, then
# one delay byte per frame in 2 ms units) followed by the raw frames.
GIF_HEADER_BYTES = 256  # ✅
GIF_MAX_FRAMES = 255  # ✅ hardware limit (frame count is one byte)
GIF_COUNT = 1  # ✅ byte 2 of the 04 72 upload command (number of animation slots)
GIF_DELAY_UNIT_MS = 2  # ✅ one delay unit = 2 ms, so 1..255 units = 2..510 ms

# The bus is USB Full-Speed (64-byte interrupt endpoint at 1 ms) and the
# keyboard writes each chunk to flash before ACKing it: measured ~0.15 s per
# 4 KB chunk, i.e. ~1.1 s of upload per 96x160 frame (112 frames = 2 min).
# Defaults stay well below the 255-frame maximum; playback itself is smooth.
DEFAULT_ANIMATION_FPS = 15
MAX_ANIMATION_FRAMES = 100  # default cap (~6.5 s at 15 fps, ~2 min upload)
UPLOAD_SECONDS_PER_CHUNK = 0.147  # measured: 841 chunks in 2:04

# --------------------------------------------------------------------------- #
# USB identity (the Vibe99 reuses Apple's VID:PID, see device/descriptors.py)
# --------------------------------------------------------------------------- #
VIBE99_VID = 0x05AC  # ✅
VIBE99_PID = 0x024F  # ✅

# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #
# Small inter-report delay (seconds) when streaming many chunks, to avoid
# overrunning the device's receive buffer during a large screen upload.
INTER_CHUNK_DELAY_S = 0.035  # Match official driver cmd_delaytime value=35
READ_TIMEOUT_MS = 1000
# After every 4096-byte screen chunk the keyboard answers on the screen
# interface with ``01 5a 02 ...`` (seen on hardware) once it has stored it; the
# official driver waits up to 300 ms for it before the next chunk, so do we.  ✅
SCREEN_ACK_TIMEOUT_MS = 300
