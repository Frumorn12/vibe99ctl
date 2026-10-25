"""RGB lighting command encoders.

Verified on a real Vibe99 (static green came out green). Same SONiX vendor
driver family as the Ajazz AK820 Pro, whose layout this matches:

1. ``04 18`` (start), ``04 13 00 00 00 00 00 00 01`` (one lighting packet follows),
2. the lighting packet, sent without readback::

       [0] effect  [1..3] R G B  [8] rainbow  [9] brightness 0-5
       [10] speed 0-5  [11] direction  [14..15] AA 55

3. ``04 02`` (commit) and ``04 F0`` (apply, no readback).

Effect ids and names are the official driver's list (``1033.lan`` 521-540);
the factory default is 11 (Rolling), brightness 5, speed 3
(``<light default_mode="11" default_brightness="5" default_speed="3"/>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..errors import ValidationError
from ..util.colors import RGB
from .packets import Packet

BRIGHTNESS_MAX = 5
SPEED_MAX = 5


class RgbEffect(IntEnum):
    """Built-in lighting effects, numbered as the keyboard firmware expects."""

    OFF = 0
    STATIC = 1
    SINGLE_ON = 2
    SINGLE_OFF = 3
    GLITTERING = 4
    FALLING = 5
    COLOURFUL = 6
    BREATH = 7
    SPECTRUM = 8
    OUTWARD = 9
    SCROLLING = 10
    ROLLING = 11
    ROTATING = 12
    EXPLODE = 13
    LAUNCH = 14
    RIPPLES = 15
    FLOWING = 16
    PULSATING = 17
    TILT = 18
    SHUTTLE = 19


@dataclass(frozen=True)
class EffectInfo:
    """Which controls an effect uses (from the vendor's default effect table)."""

    name: str
    speed: bool = True
    direction: bool = False
    color: bool = True  # accepts a fixed color (otherwise always multicolor)


EFFECTS: dict[RgbEffect, EffectInfo] = {
    RgbEffect.OFF: EffectInfo("LED Off", speed=False, color=False),
    RgbEffect.STATIC: EffectInfo("Static", speed=False),
    RgbEffect.SINGLE_ON: EffectInfo("SingleOn"),
    RgbEffect.SINGLE_OFF: EffectInfo("SingleOff"),
    RgbEffect.GLITTERING: EffectInfo("Glittering"),
    RgbEffect.FALLING: EffectInfo("Falling"),
    RgbEffect.COLOURFUL: EffectInfo("Colourful", color=False),
    RgbEffect.BREATH: EffectInfo("Breath"),
    RgbEffect.SPECTRUM: EffectInfo("Spectrum", color=False),
    RgbEffect.OUTWARD: EffectInfo("Outward"),
    RgbEffect.SCROLLING: EffectInfo("Scrolling", direction=True),
    RgbEffect.ROLLING: EffectInfo("Rolling", direction=True),
    RgbEffect.ROTATING: EffectInfo("Rotating", direction=True),
    RgbEffect.EXPLODE: EffectInfo("Explode"),
    RgbEffect.LAUNCH: EffectInfo("Launch"),
    RgbEffect.RIPPLES: EffectInfo("Ripples"),
    RgbEffect.FLOWING: EffectInfo("Flowing", direction=True),
    RgbEffect.PULSATING: EffectInfo("Pulsating"),
    RgbEffect.TILT: EffectInfo("Tilt", direction=True),
    RgbEffect.SHUTTLE: EffectInfo("Shuttle"),
}

DEFAULT_EFFECT = RgbEffect.ROLLING
DEFAULT_BRIGHTNESS = 5
DEFAULT_SPEED = 3

# Friendly names exposed in the CLI -> effect (every effect by name, plus the
# aliases earlier versions of this tool accepted).
PRESETS: dict[str, RgbEffect] = {e.name.lower().replace("_", ""): e for e in RgbEffect}
PRESETS.update(
    {
        "breathing": RgbEffect.BREATH,
        "wave": RgbEffect.SCROLLING,
        "rainbow": RgbEffect.ROLLING,
        "ripple": RgbEffect.RIPPLES,
        "reactive": RgbEffect.SINGLE_ON,
    }
)


def _check(name: str, value: int, hi: int) -> int:
    if not 0 <= value <= hi:
        raise ValidationError(f"{name} must be between 0 and {hi}, got {value}.")
    return value


def _percent_to_level(value: int, name: str, hi: int) -> int:
    """Map the CLI's 0-100 scale onto the keyboard's 0-``hi`` levels."""
    _check(name, value, 100)
    return round(value * hi / 100)


def lighting_packets(
    effect: RgbEffect | int,
    *,
    color: RGB | None = None,
    brightness: int = DEFAULT_BRIGHTNESS,
    speed: int = DEFAULT_SPEED,
    direction: int = 0,
) -> list[Packet]:
    """Low-level: set an effect with keyboard-native levels.

    ``color=None`` means rainbow/multicolor. ``brightness`` and ``speed`` are
    0-5; ``direction`` is 0 (left->right / down) or 1 (the reverse).
    """
    _check("brightness", brightness, BRIGHTNESS_MAX)
    _check("speed", speed, SPEED_MAX)
    body = bytearray(64)
    body[0] = int(effect) & 0xFF
    if effect != RgbEffect.OFF:
        r, g, b = (color.r, color.g, color.b) if color is not None else (255, 0, 0)
        body[1:4] = bytes([r, g, b])
        body[8] = 1 if color is None else 0
        body[9] = brightness
        body[10] = speed
        body[11] = 1 if direction else 0
    body[14:16] = b"\xaa\x55"
    return [
        Packet(0, raw_body=b"\x04\x18", description="rgb start"),
        Packet(0, raw_body=bytes([0x04, 0x13, 0, 0, 0, 0, 0, 0, 1]), description="rgb header"),
        Packet(0, raw_body=bytes(body), description=f"rgb effect {int(effect)}", readback=False),
        Packet(0, raw_body=b"\x04\x02", description="rgb commit"),
        Packet(0, raw_body=b"\x04\xf0", description="rgb apply", readback=False),
    ]


def set_solid_color(color: RGB, *, brightness: int = 100) -> list[Packet]:
    """Set the whole keyboard to a single static color (brightness 0-100)."""
    level = _percent_to_level(brightness, "brightness", BRIGHTNESS_MAX)
    return lighting_packets(RgbEffect.STATIC, color=color, brightness=level)


def set_effect(
    effect: RgbEffect,
    *,
    color: RGB | None = None,
    brightness: int = 100,
    speed: int = 60,
    direction: int = 0,
) -> list[Packet]:
    """Set a lighting effect (brightness and speed 0-100; no color = rainbow)."""
    return lighting_packets(
        effect,
        color=color,
        brightness=_percent_to_level(brightness, "brightness", BRIGHTNESS_MAX),
        speed=_percent_to_level(speed, "speed", SPEED_MAX),
        direction=direction,
    )


def set_brightness(brightness: int) -> list[Packet]:
    """Factory effect (rainbow Rolling) at the given brightness (0-100)."""
    level = _percent_to_level(brightness, "brightness", BRIGHTNESS_MAX)
    return lighting_packets(DEFAULT_EFFECT, brightness=level)


def turn_off() -> list[Packet]:
    """Turn the lighting off."""
    return lighting_packets(RgbEffect.OFF)
