from __future__ import annotations

import pytest

from vibe99.errors import ValidationError
from vibe99.util.colors import RGB, parse_color


@pytest.mark.parametrize(
    "text,expected",
    [
        ("#ff0000", RGB(255, 0, 0)),
        ("00ff00", RGB(0, 255, 0)),
        ("0,0,255", RGB(0, 0, 255)),
        ("255, 128, 0", RGB(255, 128, 0)),
        ("red", RGB(255, 0, 0)),
        ("WHITE", RGB(255, 255, 255)),
    ],
)
def test_parse_color_valid(text, expected):
    assert parse_color(text) == expected


@pytest.mark.parametrize("text", ["nope", "#12", "300,0,0", "1,2", ""])
def test_parse_color_invalid(text):
    with pytest.raises(ValidationError):
        parse_color(text)


def test_rgb565_packing():
    # Pure red: r=255 -> 0xF800 little-endian => 00 f8
    assert RGB(255, 0, 0).to_rgb565() == 0xF800
    assert RGB(255, 0, 0).to_rgb565_bytes() == b"\x00\xf8"
    # Pure blue: 0x001F little-endian => 1f 00
    assert RGB(0, 0, 255).to_rgb565_bytes() == b"\x1f\x00"
    # White -> 0xFFFF
    assert RGB(255, 255, 255).to_rgb565() == 0xFFFF
