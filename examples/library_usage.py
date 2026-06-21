#!/usr/bin/env python3
"""Use vibe99ctl as a library — build packets and inspect bytes, no hardware.

Run:  python examples/library_usage.py
"""

from __future__ import annotations

from vibe99.config import DEFAULT_SCREEN
from vibe99.media.image import image_to_frame
from vibe99.protocol import clock, rgb, screen
from vibe99.util.colors import parse_color


def show(title: str, packets) -> None:
    print(f"\n# {title}")
    for pkt in packets:
        print(f"  {pkt.description or hex(pkt.opcode):<28} {pkt.hex()}")


def main() -> None:
    # --- RGB -------------------------------------------------------------
    red = parse_color("#ff0000")
    show("RGB solid red @ 75%", [rgb.set_solid_color(red, brightness=75)])
    show("RGB rainbow", [rgb.set_effect(rgb.RgbEffect.RAINBOW, speed=80)])

    # --- Clock -----------------------------------------------------------
    show("Clock sync (now)", [clock.sync()])

    # --- Screen ----------------------------------------------------------
    # Build a frame buffer from an in-memory image without touching disk.
    from PIL import Image

    img = Image.new("RGB", (320, 200), (0, 128, 255))
    buf = image_to_frame(img, spec=DEFAULT_SCREEN, fit="cover")
    packets = screen.upload_frame(buf, spec=DEFAULT_SCREEN)
    print(
        f"\n# Screen upload (1 frame, {DEFAULT_SCREEN.width}x{DEFAULT_SCREEN.height} "
        f"{DEFAULT_SCREEN.pixel_format})"
    )
    print(f"  frame bytes : {len(buf)}")
    print(f"  packets     : {len(packets)} (BEGIN + DATA chunks + END)")
    print(f"  first packet: {packets[0].hex()}")


if __name__ == "__main__":
    main()
