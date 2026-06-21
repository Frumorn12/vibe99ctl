"""Clock / date-time sync command encoder.

The on-screen clock needs the host to push the current time (the keyboard has no
internet clock). The common encoding is a small BCD or raw-byte date-time
struct. We send raw bytes (year split into century/year-of-century) which is the
most frequently observed layout. ``# TO-VERIFY``.
"""

from __future__ import annotations

import datetime as _dt

from .packets import Opcode, Packet


def sync(now: _dt.datetime | None = None) -> Packet:
    """Build a clock-sync packet for ``now`` (defaults to local time)."""
    now = now or _dt.datetime.now()
    payload = bytes(
        [
            now.year // 100,  # century, e.g. 20
            now.year % 100,  # year of century, e.g. 26
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
            now.isoweekday() % 7,  # 0=Sunday .. 6=Saturday (# TO-VERIFY)
        ]
    )
    return Packet(
        Opcode.CLOCK_SYNC, payload, description=f"clock sync {now.isoformat(timespec='seconds')}"
    )
