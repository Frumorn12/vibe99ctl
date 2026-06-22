"""RGB lighting command encoders.

These build the correct packet sequences for the Mechlands Vibe99.
"""

from __future__ import annotations

from enum import IntEnum

from ..errors import ValidationError
from ..util.colors import RGB
from .packets import Packet


class RgbEffect(IntEnum):
    """Lighting effects mapped to the hardware's 1-11 modes."""

    STATIC = 0x01
    BREATHING = 0x02
    WAVE = 0x03
    RAINBOW = 0x04
    RIPPLE = 0x05
    REACTIVE = 0x06
    MODE_7 = 0x07
    MODE_8 = 0x08
    MODE_9 = 0x09
    MODE_10 = 0x0A
    MODE_11 = 0x0B
    OFF = 0x00


# Friendly names exposed in the CLI -> effect.
PRESETS: dict[str, RgbEffect] = {
    "static": RgbEffect.STATIC,
    "breathing": RgbEffect.BREATHING,
    "wave": RgbEffect.WAVE,
    "rainbow": RgbEffect.RAINBOW,
    "ripple": RgbEffect.RIPPLE,
    "reactive": RgbEffect.REACTIVE,
    "mode7": RgbEffect.MODE_7,
    "mode8": RgbEffect.MODE_8,
    "mode9": RgbEffect.MODE_9,
    "mode10": RgbEffect.MODE_10,
    "mode11": RgbEffect.MODE_11,
    "off": RgbEffect.OFF,
}


def _check_unit(name: str, value: int, lo: int = 0, hi: int = 100) -> int:
    if not lo <= value <= hi:
        raise ValidationError(f"{name} must be between {lo} and {hi}, got {value}.")
    return value


def _make_rgb_packets(
    effect: int,
    brightness: int,
    speed: int,
    direction: int,
    color: RGB | None = None,
    colorful: bool = True,
    profile: int = 1,
) -> list[Packet]:
    # Scale parameters
    # brightness: 0..100 -> 0..5
    scaled_brightness = int(round(brightness / 20.0))
    # speed: 0..100 -> 1..5
    scaled_speed = max(1, min(5, int(round(speed / 20.0))))
    # direction: 0 or 1
    scaled_direction = 1 if direction else 0
    
    # Setup color bytes
    if color is not None:
        r, g, b = color.r, color.g, color.b
        is_colorful = 0
        color_val = 0
    else:
        r, g, b = 0, 0, 0
        is_colorful = 1 if colorful else 0
        color_val = 255
        
    # Start command
    p1 = Packet(0, raw_body=b"\x04\x18", description="rgb start 1")
    # Preamble profile type
    p2 = Packet(0, raw_body=bytes([0x04, 0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, profile & 0xFF]), description="rgb start 2")
    
    # Actual RGB payload:
    # 00 [mode] [color_val] [r] [g] [b] 00 00 00 [is_colorful] [brightness] [speed] [direction] 00 00 aa 55
    body = bytearray(64)
    body[0] = effect & 0xFF
    body[1] = color_val & 0xFF
    body[2] = r & 0xFF
    body[3] = g & 0xFF
    body[4] = b & 0xFF
    body[8] = is_colorful & 0xFF
    body[9] = scaled_brightness & 0xFF
    body[10] = scaled_speed & 0xFF
    body[11] = scaled_direction & 0xFF
    body[14] = 0xaa
    body[15] = 0x55
    
    p3 = Packet(0, raw_body=bytes(body), description=f"rgb config (mode={effect})")
    
    # Commit/finish
    p4 = Packet(0, raw_body=b"\x04\x02", description="rgb commit")
    return [p1, p2, p3, p4]


def set_solid_color(
    color: RGB,
    *,
    brightness: int = 100,
    profile: int = 1,
) -> list[Packet]:
    """Set the whole keyboard to a single static color."""
    _check_unit("brightness", brightness)
    return _make_rgb_packets(
        effect=RgbEffect.STATIC,
        brightness=brightness,
        speed=1,
        direction=0,
        color=color,
        colorful=False,
        profile=profile,
    )


def set_effect(
    effect: RgbEffect,
    *,
    color: RGB | None = None,
    brightness: int = 100,
    speed: int = 50,
    direction: int = 0,
    profile: int = 1,
) -> list[Packet]:
    """Set an animated lighting effect."""
    _check_unit("brightness", brightness)
    _check_unit("speed", speed)
    return _make_rgb_packets(
        effect=effect,
        brightness=brightness,
        speed=speed,
        direction=direction,
        color=color,
        colorful=(color is None),
        profile=profile,
    )


def set_brightness(brightness: int, profile: int = 1) -> list[Packet]:
    """Change only the global brightness (0-100)."""
    _check_unit("brightness", brightness)
    # Default to active Mode 11 (the device default out-of-the-box)
    return _make_rgb_packets(
        effect=RgbEffect.MODE_11,
        brightness=brightness,
        speed=50,
        direction=0,
        colorful=True,
        profile=profile,
    )


def turn_off(profile: int = 1) -> list[Packet]:
    """Turn the lighting off."""
    return set_effect(RgbEffect.OFF, brightness=0, profile=profile)
