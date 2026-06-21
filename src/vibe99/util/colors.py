"""Color parsing and conversion helpers.

Accepts the formats a CLI user actually types: ``#RRGGBB``, ``RRGGBB``,
``r,g,b``, and a handful of named colors. Everything funnels into a normalized
``RGB`` tuple that the protocol layer consumes.
"""

from __future__ import annotations

import re
import struct
from typing import NamedTuple

from ..errors import ValidationError


class RGB(NamedTuple):
    r: int
    g: int
    b: int

    def as_bytes(self) -> bytes:
        return bytes((self.r, self.g, self.b))

    def to_rgb565(self) -> int:
        """Pack into a 16-bit RGB565 value (host int)."""
        return ((self.r & 0xF8) << 8) | ((self.g & 0xFC) << 3) | (self.b >> 3)

    def to_rgb565_bytes(self, little_endian: bool = True) -> bytes:
        fmt = "<H" if little_endian else ">H"
        return struct.pack(fmt, self.to_rgb565())


NAMED_COLORS: dict[str, RGB] = {
    "black": RGB(0, 0, 0),
    "white": RGB(255, 255, 255),
    "red": RGB(255, 0, 0),
    "green": RGB(0, 255, 0),
    "blue": RGB(0, 0, 255),
    "yellow": RGB(255, 255, 0),
    "cyan": RGB(0, 255, 255),
    "magenta": RGB(255, 0, 255),
    "orange": RGB(255, 128, 0),
    "purple": RGB(128, 0, 128),
    "pink": RGB(255, 105, 180),
    "warmwhite": RGB(255, 214, 170),
    "coolwhite": RGB(200, 220, 255),
}

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
_TRIPLET_RE = re.compile(r"^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$")


def _clamp_channel(value: int) -> int:
    if not 0 <= value <= 255:
        raise ValidationError(f"Color channel out of range (0-255): {value}")
    return value


def parse_color(text: str) -> RGB:
    """Parse a user-supplied color string into an :class:`RGB`."""
    if text is None:
        raise ValidationError("No color provided.")
    s = text.strip().lower()

    if s in NAMED_COLORS:
        return NAMED_COLORS[s]

    m = _HEX_RE.match(s)
    if m:
        h = m.group(1)
        return RGB(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    m = _TRIPLET_RE.match(s)
    if m:
        return RGB(
            _clamp_channel(int(m.group(1))),
            _clamp_channel(int(m.group(2))),
            _clamp_channel(int(m.group(3))),
        )

    raise ValidationError(
        f"Could not parse color {text!r}. Use '#RRGGBB', 'R,G,B', or a name "
        f"({', '.join(sorted(NAMED_COLORS))})."
    )


def available_names() -> list[str]:
    return sorted(NAMED_COLORS)
