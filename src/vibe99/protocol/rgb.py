"""RGB lighting command encoders.

These build :class:`~vibe99.protocol.packets.Packet` objects. The exact opcode
layout is unconfirmed (``# TO-VERIFY``); the structure mirrors how the vast
majority of these HID keyboards encode lighting: one byte each for
mode/brightness/speed, three bytes RGB, plus an optional direction byte.
"""

from __future__ import annotations

from enum import IntEnum

from ..errors import ValidationError
from ..util.colors import RGB
from .packets import Opcode, Packet


class RgbEffect(IntEnum):
    """Lighting effects. Values are placeholders until confirmed (# TO-VERIFY)."""

    STATIC = 0x01
    BREATHING = 0x02
    WAVE = 0x03
    RAINBOW = 0x04
    RIPPLE = 0x05
    REACTIVE = 0x06
    OFF = 0x00


# Friendly names exposed in the CLI -> effect.
PRESETS: dict[str, RgbEffect] = {
    "static": RgbEffect.STATIC,
    "breathing": RgbEffect.BREATHING,
    "wave": RgbEffect.WAVE,
    "rainbow": RgbEffect.RAINBOW,
    "ripple": RgbEffect.RIPPLE,
    "reactive": RgbEffect.REACTIVE,
    "off": RgbEffect.OFF,
}


def _check_unit(name: str, value: int, lo: int = 0, hi: int = 100) -> int:
    if not lo <= value <= hi:
        raise ValidationError(f"{name} must be between {lo} and {hi}, got {value}.")
    return value


def set_solid_color(
    color: RGB,
    *,
    brightness: int = 100,
) -> Packet:
    """Set the whole keyboard to a single static color."""
    _check_unit("brightness", brightness)
    payload = bytes(
        [
            RgbEffect.STATIC,
            brightness,
            0,  # speed (unused for static)
            color.r,
            color.g,
            color.b,
            0,  # direction
        ]
    )
    return Packet(Opcode.RGB, payload, description=f"rgb static {color}")


def set_effect(
    effect: RgbEffect,
    *,
    color: RGB | None = None,
    brightness: int = 100,
    speed: int = 50,
    direction: int = 0,
) -> Packet:
    """Set an animated lighting effect.

    ``color`` is optional: rainbow-style effects ignore it. When omitted, the
    color bytes are left at zero so the firmware uses its own palette.
    """
    _check_unit("brightness", brightness)
    _check_unit("speed", speed)
    r, g, b = (color.r, color.g, color.b) if color else (0, 0, 0)
    payload = bytes([effect, brightness, speed, r, g, b, direction & 0xFF])
    return Packet(Opcode.RGB, payload, description=f"rgb effect {effect.name.lower()}")


def set_brightness(brightness: int) -> Packet:
    """Change only the global brightness (0-100)."""
    _check_unit("brightness", brightness)
    # Sub-command 0x01 = "brightness only" (# TO-VERIFY).
    return Packet(
        Opcode.RGB, bytes([0xFF, brightness]), sub=0x01, description=f"rgb brightness {brightness}"
    )


def turn_off() -> Packet:
    """Turn the lighting off."""
    return set_effect(RgbEffect.OFF, brightness=0)
