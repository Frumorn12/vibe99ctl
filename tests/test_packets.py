from __future__ import annotations

import pytest

from vibe99.config import HID_REPORT_SIZE
from vibe99.errors import ProtocolError
from vibe99.protocol.packets import (
    Packet,
    build_report,
    checksum_sum8,
    checksum_xor,
    crc16_ccitt,
    frame,
)


def test_checksum_sum8():
    assert checksum_sum8(b"\x01\x02\x03") == 0x06
    assert checksum_sum8(b"\xff\x01") == 0x00  # wraps


def test_checksum_xor():
    assert checksum_xor(b"\x01\x02") == 0x03
    assert checksum_xor(b"\xff\xff") == 0x00


def test_crc16_ccitt_known_vector():
    # CRC-16/CCITT-FALSE of b"123456789" is 0x29B1.
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_build_report_pads_and_prefixes_report_id():
    report = build_report(b"\xaa\xbb", report_id=0x00)
    assert len(report) == HID_REPORT_SIZE + 1
    assert report[0] == 0x00
    assert report[1:3] == b"\xaa\xbb"
    assert report[3:] == b"\x00" * (HID_REPORT_SIZE - 2)


def test_build_report_rejects_oversized_payload():
    with pytest.raises(ProtocolError):
        build_report(b"\x00" * (HID_REPORT_SIZE + 1))


def test_frame_layout_and_checksum():
    body = frame(0x06, b"\x01\x02", sub=0x03)
    assert len(body) == HID_REPORT_SIZE
    assert body[0] == 0x06  # opcode
    assert body[1] == 0x03  # sub
    assert body[2] == 0x02  # payload length
    assert body[3:5] == b"\x01\x02"
    # checksum over [opcode, sub, len, payload]
    expected = checksum_sum8(bytes([0x06, 0x03, 0x02, 0x01, 0x02]))
    assert body[5] == expected


def test_frame_rejects_too_long_payload():
    with pytest.raises(ProtocolError):
        frame(0x06, b"\x00" * HID_REPORT_SIZE)


def test_packet_to_report_roundtrip():
    pkt = Packet(0x06, b"\x10", sub=0x00, description="demo")
    report = pkt.to_report()
    assert len(report) == HID_REPORT_SIZE + 1
    assert report[0] == 0x00  # report id
    assert report[1] == 0x06  # opcode
    assert "demo" not in pkt.hex()  # hex() returns bytes only
