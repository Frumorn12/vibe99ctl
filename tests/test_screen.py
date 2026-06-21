from __future__ import annotations

import pytest

from vibe99.config import ScreenSpec
from vibe99.errors import ValidationError
from vibe99.protocol.packets import Opcode
from vibe99.protocol.screen import DATA_CHUNK_BYTES, upload_animation, upload_frame


def test_upload_frame_packet_sequence():
    spec = ScreenSpec(width=16, height=16, pixel_format="rgb565-le")
    buffer = b"\x00" * spec.frame_bytes
    packets = upload_frame(buffer, spec=spec)

    assert packets[0].opcode == Opcode.SCREEN_BEGIN
    assert packets[-1].opcode == Opcode.SCREEN_END
    data_packets = [p for p in packets if p.opcode == Opcode.SCREEN_DATA]

    expected_chunks = (spec.frame_bytes + DATA_CHUNK_BYTES - 1) // DATA_CHUNK_BYTES
    assert len(data_packets) == expected_chunks


def test_upload_frame_rejects_wrong_size():
    spec = ScreenSpec(width=16, height=16)
    with pytest.raises(ValidationError):
        upload_frame(b"\x00" * 10, spec=spec)


def test_upload_animation_brackets_frames():
    spec = ScreenSpec(width=8, height=8, pixel_format="rgb565-le")
    frame = b"\x00" * spec.frame_bytes
    packets = upload_animation([frame, frame], spec=spec, fps=5)

    assert packets[0].opcode == Opcode.SCREEN_MODE
    begins = [p for p in packets if p.opcode == Opcode.SCREEN_BEGIN]
    assert len(begins) == 2  # one per frame


def test_upload_animation_rejects_empty():
    with pytest.raises(ValidationError):
        upload_animation([])
