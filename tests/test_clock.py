from __future__ import annotations

import datetime as dt

from vibe99.protocol.clock import sync


def test_clock_sync_payload_layout():
    when = dt.datetime(2026, 6, 21, 13, 45, 30)
    packets = sync(when)
    assert len(packets) == 4

    assert packets[0].body().startswith(b"\x04\x18")
    assert packets[1].body().startswith(b"\x04\x28\x00\x00\x00\x00\x00\x00\x01")
    assert packets[3].body().startswith(b"\x04\x02")

    body = packets[2].body()
    assert body[0] == 0x00
    assert body[1] == 0x01  # profile 1
    assert body[2] == 0x5A
    assert body[3] == 26
    assert body[4] == 6
    assert body[5] == 21
    assert body[6] == 13
    assert body[7] == 45
    assert body[8] == 30
    assert body[9] == 0x00
    assert body[10] == 7  # 2026-06-21 is Sunday
    assert body[62] == 0xAA
    assert body[63] == 0x55


def test_clock_sync_defaults_to_now():
    packets = sync()
    assert len(packets) == 4
    assert len(packets[2].body()) == 64
