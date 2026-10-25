"""Screen (TFT) command encoders.

Implements the Mechlands Vibe99 TFT protocol, verified on hardware:

1. ``04 18`` on the control interface (start of a config session),
2. ``04 72 <gif_count> 00 00 00 00 00 <chunks lo> <chunks hi>`` (upload header),
3. ``chunks`` x 4096-byte output reports on the screen interface, each
   acknowledged by the keyboard (the runner waits for the ACK),
4. ``04 02`` (commit to flash).

The data stream is a 256-byte header (frame count, one delay byte per frame in
2 ms units, ``0xFF`` padding) followed by the raw frames, ``0xFF``-padded to a
whole number of chunks. A static image is simply a one-frame animation.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..config import (
    DEFAULT_SCREEN,
    GIF_COUNT,
    GIF_DELAY_UNIT_MS,
    GIF_HEADER_BYTES,
    GIF_MAX_FRAMES,
    SCREEN_REPORT_SIZE,
    ScreenSpec,
)
from ..errors import ValidationError
from .packets import Packet


def delay_units(delay_ms: float) -> int:
    """Convert a frame delay in ms to the header's 2 ms units (clamped 1..255)."""
    return max(1, min(255, round(delay_ms / GIF_DELAY_UNIT_MS)))


def build_payload(frames: Sequence[bytes], units: Sequence[int]) -> bytes:
    """Header + frames, ``0xFF``-padded to a multiple of the chunk size."""
    header = bytearray(b"\xff" * GIF_HEADER_BYTES)
    header[0] = len(frames)
    for i, u in enumerate(units):
        header[1 + i] = u & 0xFF
    payload = bytes(header) + b"".join(frames)
    return payload + b"\xff" * (-len(payload) % SCREEN_REPORT_SIZE)


def _make_screen_packets(frames: Sequence[bytes], units: Sequence[int]) -> list[Packet]:
    """Package frames into the exact Vibe99 stream sequence."""
    payload = build_payload(frames, units)
    num_chunks = len(payload) // SCREEN_REPORT_SIZE

    start = Packet(0, raw_body=b"\x04\x18", description="screen upload start")
    init_body = bytearray(64)
    init_body[0:3] = bytes([0x04, 0x72, GIF_COUNT])
    init_body[8] = num_chunks & 0xFF
    init_body[9] = (num_chunks >> 8) & 0xFF
    init = Packet(0, raw_body=bytes(init_body), description="screen upload init")

    packets = [start, init]
    for i in range(num_chunks):
        packets.append(
            Packet(
                0,
                raw_body=payload[i * SCREEN_REPORT_SIZE : (i + 1) * SCREEN_REPORT_SIZE],
                report_size=SCREEN_REPORT_SIZE,
                description=f"screen chunk {i + 1}/{num_chunks}",
            )
        )
    packets.append(Packet(0, raw_body=b"\x04\x02", description="screen upload commit"))
    return packets


def _check_frames(frames: Sequence[bytes], spec: ScreenSpec) -> None:
    if not frames:
        raise ValidationError("Animation has no frames.")
    if len(frames) > GIF_MAX_FRAMES:
        raise ValidationError(
            f"{len(frames)} frames, but the keyboard stores at most {GIF_MAX_FRAMES}."
        )
    for f in frames:
        if len(f) != spec.frame_bytes:
            raise ValidationError(
                f"Frame buffer is {len(f)} bytes but screen expects "
                f"{spec.frame_bytes} ({spec.width}x{spec.height} {spec.pixel_format})."
            )


def upload_frame(
    buffer: bytes,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    frame_index: int = 0,
) -> list[Packet]:
    """Build the packet sequence to upload one static frame buffer."""
    _check_frames([buffer], spec)
    return _make_screen_packets([buffer], [0])


def upload_animation(
    frames: Sequence[bytes],
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fps: float = 5,
    delays_ms: Sequence[float] | None = None,
) -> list[Packet]:
    """Build the packet sequence to upload a multi-frame animation.

    Each frame shows for ``delays_ms[i]`` (as stored in a GIF), or for
    ``1000 / fps`` ms when no per-frame delays are given. The keyboard's delay
    field tops out at 510 ms per frame.
    """
    _check_frames(frames, spec)
    if delays_ms is None:
        delays_ms = [1000.0 / fps] * len(frames)
    elif len(delays_ms) != len(frames):
        raise ValidationError(f"{len(delays_ms)} delays given for {len(frames)} frames.")
    return _make_screen_packets(frames, [delay_units(d) for d in delays_ms])


def set_display_mode(mode: int) -> list[Packet]:
    """Switch the on-screen display mode (clock face, custom image, etc.)."""
    p0 = Packet(0, raw_body=b"\x04\xf0", description="screen mode start")
    p1 = Packet(
        0,
        raw_body=bytes([0x04, 0xF5, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, mode & 0xFF]),
        description=f"screen mode {mode}",
    )
    p2 = Packet(0, raw_body=b"\x04\x02", description="screen mode commit")
    return [p0, p1, p2]
