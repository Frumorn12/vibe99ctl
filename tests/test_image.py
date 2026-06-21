from __future__ import annotations

from PIL import Image

from vibe99.config import ScreenSpec
from vibe99.media.image import image_to_frame, to_rgb565


def test_to_rgb565_length_and_value():
    img = Image.new("RGB", (2, 1), (255, 0, 0))
    buf = to_rgb565(img)
    assert len(buf) == 2 * 1 * 2  # 2 px * 2 bytes
    # each pixel is 0xF800 little-endian -> 00 f8
    assert buf == b"\x00\xf8\x00\xf8"


def test_image_to_frame_matches_screen_bytes(solid_image):
    spec = ScreenSpec(width=240, height=240, pixel_format="rgb565-le")
    frame = image_to_frame(solid_image, spec=spec, fit="stretch")
    assert len(frame) == spec.frame_bytes


def test_image_to_frame_resizes_arbitrary_input():
    spec = ScreenSpec(width=64, height=64, pixel_format="rgb565-le")
    img = Image.new("RGB", (200, 100), (0, 255, 0))
    for fit in ("contain", "cover", "stretch"):
        frame = image_to_frame(img, spec=spec, fit=fit)
        assert len(frame) == spec.frame_bytes


def test_rgb888_format():
    spec = ScreenSpec(width=4, height=4, pixel_format="rgb888")
    img = Image.new("RGB", (4, 4), (10, 20, 30))
    frame = image_to_frame(img, spec=spec, fit="stretch")
    assert len(frame) == 4 * 4 * 3
    assert frame[:3] == bytes((10, 20, 30))
