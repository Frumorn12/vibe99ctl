from __future__ import annotations

import pytest

from vibe99.errors import ValidationError
from vibe99.protocol.rgb import PRESETS, RgbEffect, lighting_packets, set_solid_color, turn_off
from vibe99.util.colors import RGB


def test_static_green_layout_verified_on_hardware():
    packets = set_solid_color(RGB(0, 255, 0), brightness=100)
    bodies = [p.body() for p in packets]
    assert bodies[0][:2] == b"\x04\x18"
    assert bodies[1][:9] == b"\x04\x13\x00\x00\x00\x00\x00\x00\x01"
    assert bodies[2][:16] == bytes.fromhex("01 00 ff 00 00 00 00 00 00 05 03 00 00 00 aa 55")
    assert bodies[3][:2] == b"\x04\x02"
    assert bodies[4][:2] == b"\x04\xf0"
    # the official driver reads back the control commands, not the payload/apply
    assert [p.readback for p in packets] == [True, True, False, True, False]


def test_no_color_means_rainbow():
    body = lighting_packets(RgbEffect.ROLLING, speed=3, direction=1)[2].body()
    assert body[0] == 11 and body[8] == 1 and body[10] == 3 and body[11] == 1


def test_off_has_only_mode_and_trailer():
    body = turn_off()[2].body()
    assert body[:14] == bytes(14) and body[14:16] == b"\xaa\x55"


def test_levels_are_validated():
    with pytest.raises(ValidationError):
        lighting_packets(RgbEffect.STATIC, brightness=6)


def test_presets_cover_every_effect_and_old_aliases():
    assert PRESETS["singleon"] is RgbEffect.SINGLE_ON
    assert PRESETS["rainbow"] is RgbEffect.ROLLING
    assert set(RgbEffect) <= set(PRESETS.values())
