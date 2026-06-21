from __future__ import annotations

import datetime as dt

from vibe99.protocol.clock import sync
from vibe99.protocol.packets import Opcode


def test_clock_sync_payload_layout():
    when = dt.datetime(2026, 6, 21, 13, 45, 30)
    pkt = sync(when)
    assert pkt.opcode == Opcode.CLOCK_SYNC
    # payload: century, yy, month, day, hour, minute, second, weekday
    assert pkt.payload[0] == 20
    assert pkt.payload[1] == 26
    assert pkt.payload[2] == 6
    assert pkt.payload[3] == 21
    assert pkt.payload[4] == 13
    assert pkt.payload[5] == 45
    assert pkt.payload[6] == 30


def test_clock_sync_defaults_to_now():
    pkt = sync()
    assert pkt.opcode == Opcode.CLOCK_SYNC
    assert len(pkt.payload) == 8
