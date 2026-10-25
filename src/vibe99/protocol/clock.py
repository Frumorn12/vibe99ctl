"""Clock / date-time sync command encoder.

The on-screen clock needs the host to push the current time (the keyboard has no
internet clock). The common encoding is a small BCD or raw-byte date-time
struct. We send raw bytes (year split into century/year-of-century) which is the
most frequently observed layout. ``# TO-VERIFY``.
"""

from __future__ import annotations

import datetime as _dt

from .packets import Packet


def sync(now: _dt.datetime | None = None, profile: int = 1) -> list[Packet]:
    """Build a clock-sync packet sequence for ``now`` (defaults to local time)."""
    now = now or _dt.datetime.now()
    # Preamble start
    p1 = Packet(0, raw_body=b"\x04\x18", description="clock sync start 1")
    # Preamble sync type
    p2 = Packet(
        0,
        raw_body=bytes([0x04, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, profile & 0xFF]),
        description="clock sync start 2",
    )
    # Actual clock payload
    # year % 100, month, day, hour, minute, second, 0x00, day_of_week (1 = Mon, 7 = Sun)
    time_bytes = bytes(
        [
            now.year % 100,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
            0x00,
            now.isoweekday(),
        ]
    )
    # The clock payload packet starts with 00 [profile] 5a followed by 8 time
    # bytes, padded with 0x00 to byte 62, and ending with aa 55
    body = bytearray([0x00, profile & 0xFF, 0x5A]) + time_bytes
    body = body + b"\x00" * (62 - len(body)) + b"\xaa\x55"
    p3 = Packet(
        0, raw_body=bytes(body), description=f"clock sync {now.isoformat(timespec='seconds')}"
    )
    # Commit/finish
    p4 = Packet(0, raw_body=b"\x04\x02", description="clock sync commit")
    return [p1, p2, p3, p4]
