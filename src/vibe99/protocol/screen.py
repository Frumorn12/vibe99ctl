"""Screen (TFT) command encoders.

The Vibe99 has a 1.06" TFT. Uploading a frame to this class of device almost
always follows a three-phase pattern over HID:

    BEGIN  -> announce a transfer (dimensions, total size, mode, frame index)
    DATA   -> stream the pixel buffer in fixed-size chunks (with chunk index)
    END    -> commit / display

This module turns a raw pixel buffer (already in the device's pixel format, see
:mod:`vibe99.media.image`) into the corresponding sequence of packets. The
opcodes and header fields are ``# TO-VERIFY``; the *shape* is correct for the
device class.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator

from ..config import DEFAULT_SCREEN, SCREEN_REPORT_SIZE, ScreenSpec
from ..errors import ValidationError
from .packets import Opcode, Packet

# The screen interface (vendor usage page 0xFF68) takes a 4096-byte output report
# (confirmed from the report descriptor). We can therefore stream pixel data in
# ~4 KB chunks instead of 64-byte dribbles: a 240x240 RGB565 frame (115200 B)
# becomes ~29 reports rather than ~2000.
#
# Reserve room for the framing header (opcode/sub/len/checksum) plus a per-chunk
# sub-header (chunk_index u16 + reserved u16). Exact layout is # TO-VERIFY.
_CHUNK_SUBHEADER = 4
DATA_CHUNK_BYTES = SCREEN_REPORT_SIZE - 4 - _CHUNK_SUBHEADER


def _begin(spec: ScreenSpec, total_bytes: int, frame_index: int) -> Packet:
    payload = struct.pack(
        "<HHIB",
        spec.width,
        spec.height,
        total_bytes,
        frame_index & 0xFF,
    )
    return Packet(
        Opcode.SCREEN_BEGIN, payload, description="screen begin", report_size=SCREEN_REPORT_SIZE
    )


def _data_chunks(buffer: bytes) -> Iterator[Packet]:
    total = len(buffer)
    chunk_count = (total + DATA_CHUNK_BYTES - 1) // DATA_CHUNK_BYTES
    for i in range(chunk_count):
        start = i * DATA_CHUNK_BYTES
        chunk = buffer[start : start + DATA_CHUNK_BYTES]
        sub_header = struct.pack("<HH", i, 0)
        yield Packet(
            Opcode.SCREEN_DATA,
            sub_header + chunk,
            sub=i & 0xFF,
            description=f"screen data chunk {i + 1}/{chunk_count}",
            report_size=SCREEN_REPORT_SIZE,
        )


def _end(frame_index: int) -> Packet:
    return Packet(
        Opcode.SCREEN_END,
        bytes([frame_index & 0xFF]),
        description="screen end/commit",
        report_size=SCREEN_REPORT_SIZE,
    )


def upload_frame(
    buffer: bytes,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    frame_index: int = 0,
) -> list[Packet]:
    """Build the full packet sequence to upload one frame buffer.

    :param buffer: raw pixel bytes in the device's pixel format. Its length must
        match ``spec.frame_bytes``.
    """
    if len(buffer) != spec.frame_bytes:
        raise ValidationError(
            f"Frame buffer is {len(buffer)} bytes but screen expects "
            f"{spec.frame_bytes} ({spec.width}x{spec.height} "
            f"{spec.pixel_format})."
        )
    packets: list[Packet] = [_begin(spec, len(buffer), frame_index)]
    packets.extend(_data_chunks(buffer))
    packets.append(_end(frame_index))
    return packets


def upload_animation(
    frames: list[bytes],
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fps: int = 5,
) -> list[Packet]:
    """Build the packet sequence to upload a multi-frame animation.

    The animation is sent frame-by-frame using :func:`upload_frame` with an
    incrementing frame index, bracketed by a mode packet that declares the frame
    count and playback rate. (Whether the device stores animations on-board or
    needs the host to drive playback is ``# TO-VERIFY``; storing on-board is the
    documented Vibe99 behaviour for GIFs.)
    """
    if not frames:
        raise ValidationError("Animation has no frames.")
    mode = Packet(
        Opcode.SCREEN_MODE,
        struct.pack("<BB", len(frames) & 0xFF, fps & 0xFF),
        description="screen animation mode",
    )
    packets: list[Packet] = [mode]
    for idx, frame in enumerate(frames):
        packets.extend(upload_frame(frame, spec=spec, frame_index=idx))
    return packets


def set_display_mode(mode: int) -> Packet:
    """Switch the on-screen display mode (clock face, custom image, etc.)."""
    return Packet(
        Opcode.SCREEN_MODE, bytes([mode & 0xFF]), sub=0xFF, description=f"screen mode {mode}"
    )
