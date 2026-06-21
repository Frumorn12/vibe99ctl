"""Low-level packet framing and checksum primitives.

Frame model (best-effort, ``# TO-VERIFY`` against real captures)::

    byte 0      : Report ID (only present on the wire if HID_REPORT_ID != 0)
    byte 1      : opcode          (command family, e.g. RGB / SCREEN / CLOCK)
    byte 2      : sub / sequence  (sub-command or chunk index)
    byte 3      : payload length  (number of meaningful payload bytes)
    byte 4..N-2 : payload
    byte N-1    : checksum        (algorithm: see CHECKSUM)

The whole thing is padded with 0x00 up to ``HID_REPORT_SIZE``.

If a capture shows a different layout, change ``frame`` and ``CHECKSUM`` here and
nothing else in the codebase needs to move.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..config import HID_REPORT_ID, HID_REPORT_SIZE
from ..errors import ProtocolError


class Opcode(IntEnum):
    """Command families. Values are placeholders until confirmed (# TO-VERIFY)."""

    DEVICE_INFO = 0x01
    RGB = 0x06
    SCREEN_BEGIN = 0x10
    SCREEN_DATA = 0x11
    SCREEN_END = 0x12
    SCREEN_MODE = 0x13
    CLOCK_SYNC = 0x20
    PING = 0xF0


# --------------------------------------------------------------------------- #
# Checksums — several are provided so the RE work can drop in the right one.
# --------------------------------------------------------------------------- #
def checksum_sum8(data: bytes) -> int:
    """8-bit modular sum (very common on cheap HID firmware)."""
    return sum(data) & 0xFF


def checksum_xor(data: bytes) -> int:
    """8-bit XOR of all bytes."""
    acc = 0
    for b in data:
        acc ^= b
    return acc & 0xFF


def crc16_ccitt(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE. Returned as a 16-bit int."""
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


# Active checksum used by ``frame``. Swap this once the algorithm is known.
CHECKSUM = staticmethod(checksum_sum8)


def build_report(
    payload: bytes, *, report_id: int = HID_REPORT_ID, size: int = HID_REPORT_SIZE
) -> bytes:
    """Pad ``payload`` into a fixed-size HID output report.

    ``hidapi`` always expects the first byte to be the Report ID (use 0x00 when
    the device does not use numbered reports). The total length it expects is
    ``size + 1`` in that case.
    """
    if len(payload) > size:
        raise ProtocolError(f"Payload of {len(payload)} bytes exceeds report size {size}.")
    body = bytes(payload) + b"\x00" * (size - len(payload))
    return bytes([report_id & 0xFF]) + body


def frame(opcode: int, payload: bytes = b"", *, sub: int = 0) -> bytes:
    """Build a framed command body (without the leading Report ID byte).

    The result is exactly ``HID_REPORT_SIZE`` bytes (the body), ready to be
    handed to :func:`build_report`.
    """
    if len(payload) > HID_REPORT_SIZE - 4:
        raise ProtocolError(
            f"Payload too long for a single frame: {len(payload)} bytes "
            f"(max {HID_REPORT_SIZE - 4})."
        )
    header = bytes([opcode & 0xFF, sub & 0xFF, len(payload) & 0xFF])
    without_checksum = header + bytes(payload)
    checksum = CHECKSUM(without_checksum)
    body = without_checksum + bytes([checksum])
    return body + b"\x00" * (HID_REPORT_SIZE - len(body))


@dataclass
class Packet:
    """A single command, framing-agnostic at the call site.

    Command builders create ``Packet`` objects; the runner turns them into wire
    bytes via :meth:`to_report`. This keeps the encoders declarative and easy to
    snapshot-test.
    """

    opcode: int
    payload: bytes = b""
    sub: int = 0
    description: str = ""

    def body(self) -> bytes:
        """The framed body (no leading Report ID)."""
        return frame(self.opcode, self.payload, sub=self.sub)

    def to_report(self) -> bytes:
        """Full HID output report including the leading Report ID byte."""
        return build_report(self.body())

    def hex(self) -> str:
        return self.to_report().hex(" ")
