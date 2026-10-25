from __future__ import annotations

import pytest

from vibe99.config import ScreenSpec
from vibe99.errors import ValidationError
from vibe99.protocol.screen import upload_animation, upload_frame


def test_upload_frame_packet_sequence():
    spec = ScreenSpec(width=16, height=16, pixel_format="rgb565-le")
    buffer = b"\x00" * spec.frame_bytes
    packets = upload_frame(buffer, spec=spec)

    assert len(packets) == 4
    assert packets[0].body().startswith(b"\x04\x18")
    # byte 2 = gif_count (1), bytes 8-9 = chunk count; verified on hardware
    assert packets[1].body()[:10] == b"\x04\x72\x01\x00\x00\x00\x00\x00\x01\x00"
    assert packets[2].report_size == 4096
    assert packets[3].body().startswith(b"\x04\x02")


def test_upload_frame_rejects_wrong_size():
    spec = ScreenSpec(width=16, height=16)
    with pytest.raises(ValidationError):
        upload_frame(b"\x00" * 10, spec=spec)


def test_upload_animation_brackets_frames():
    spec = ScreenSpec(width=8, height=8, pixel_format="rgb565-le")
    frame_buf = b"\x00" * spec.frame_bytes
    packets = upload_animation([frame_buf, frame_buf], spec=spec, fps=5)

    # 256 header + 2 * 128 pixels = 512 bytes -> 1 chunk
    assert len(packets) == 4
    assert packets[0].body().startswith(b"\x04\x18")
    assert packets[1].body().startswith(b"\x04\x72\x01")
    assert packets[2].report_size == 4096

    # Check that delay in header is 100 (which is 200ms / 2)
    # fps=5 -> 200ms delay -> 100 units
    data_body = packets[2].body()
    assert data_body[0] == 2  # 2 frames
    assert data_body[1] == 100  # delay frame 0
    assert data_body[2] == 100  # delay frame 1
    assert data_body[3] == 0xFF  # pad


def test_upload_animation_rejects_empty():
    with pytest.raises(ValidationError):
        upload_animation([])


def test_set_display_mode_sequence():
    from vibe99.protocol.screen import set_display_mode

    packets = set_display_mode(9)
    assert len(packets) == 3
    assert packets[0].body().startswith(b"\x04\xf0")
    assert packets[1].body().startswith(b"\x04\xf5\x00\x00\x00\x00\x00\x00\x09")
    assert packets[2].body().startswith(b"\x04\x02")


def test_payload_is_ff_padded_to_whole_chunks():
    spec = ScreenSpec(width=96, height=160)
    packets = upload_frame(b"\x00" * spec.frame_bytes, spec=spec)
    chunks = [p for p in packets if p.report_size == 4096]
    # 256 + 30720 bytes -> 8 chunks of 4096, as the keyboard ACKed in testing
    assert len(chunks) == 8
    assert packets[1].body()[8] == 8
    assert chunks[0].body()[:2] == b"\x01\x00"  # 1 frame, static
    assert chunks[0].body()[2:256] == b"\xff" * 254
    assert chunks[-1].body().endswith(b"\xff" * 100)


def test_upload_animation_uses_per_frame_delays():
    spec = ScreenSpec(width=8, height=8)
    frame = b"\x00" * spec.frame_bytes
    packets = upload_animation([frame] * 3, spec=spec, delays_ms=[40, 1000, 1])
    header = packets[2].body()
    assert list(header[:4]) == [3, 20, 255, 1]  # 2 ms units, clamped to 1..255


def test_upload_animation_rejects_too_many_frames():
    spec = ScreenSpec(width=2, height=2)
    with pytest.raises(ValidationError):
        upload_animation([b"\x00" * spec.frame_bytes] * 256, spec=spec)
