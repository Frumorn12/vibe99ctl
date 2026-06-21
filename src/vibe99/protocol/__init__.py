"""Protocol layer: packet framing, checksums, and command encoders.

The framing here is a *model*, not gospel. It is structured so that, once the
real protocol is captured (see ``docs/reverse-engineering.md``), only the
constants and the ``frame``/checksum functions need to change — the CLI and the
command builders stay the same.
"""

from __future__ import annotations

from . import clock, rgb, screen
from .packets import (
    Packet,
    build_report,
    checksum_sum8,
    checksum_xor,
    crc16_ccitt,
    frame,
)

__all__ = [
    "Packet",
    "build_report",
    "checksum_sum8",
    "checksum_xor",
    "clock",
    "crc16_ccitt",
    "frame",
    "rgb",
    "screen",
]
