"""Screen (TFT) command encoders.

Implements the Mechlands Vibe99 TFT protocol.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..config import DEFAULT_SCREEN, ScreenSpec
from ..errors import ValidationError
from .packets import Packet


def _make_screen_packets(
    frames: list[bytes],
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    delay_units: int = 30, # 60ms default
    mode: int = 2, # 2 = static, 3 = animation
) -> list[Packet]:
    """Helper to package frames and header into the exact Vibe99 stream sequence."""
    num_frames = len(frames)
    
    # 1. Build the 256-byte GIF/animation header
    header = bytearray(256)
    header[0] = num_frames & 0xFF
    for i in range(num_frames):
        header[1 + i] = delay_units & 0xFF
    for i in range(num_frames, 255):
        header[1 + i] = 0xFF
        
    # 2. Concatenate header and raw pixel buffers
    full_payload = bytes(header) + b"".join(frames)
    
    # 3. Calculate number of 4096-byte chunks
    num_chunks = (len(full_payload) + 4095) // 4096
    
    # 4. Assemble the packet sequence
    # Start/unlock command
    p1 = Packet(0, raw_body=b"\x04\x18", description="screen upload start 1")
    
    # Screen init command with mode and chunk count
    init_body = bytearray(64)
    init_body[0] = 0x04
    init_body[1] = 0x72
    init_body[2] = mode & 0xFF
    init_body[8] = num_chunks & 0xFF
    init_body[9] = (num_chunks >> 8) & 0xFF
    p2 = Packet(0, raw_body=bytes(init_body), description="screen upload init")
    
    packets = [p1, p2]
    
    # Pixel data chunks (size 4096)
    for i in range(num_chunks):
        start = i * 4096
        chunk_data = full_payload[start : start + 4096]
        if len(chunk_data) < 4096:
            chunk_data = chunk_data + b"\x00" * (4096 - len(chunk_data))
        packets.append(
            Packet(
                0,
                raw_body=chunk_data,
                report_size=4096,
                description=f"screen chunk {i+1}/{num_chunks}",
            )
        )
        
    # Commit/finish command
    p3 = Packet(0, raw_body=b"\x04\x02", description="screen upload commit")
    packets.append(p3)
    
    return packets


def upload_frame(
    buffer: bytes,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    frame_index: int = 0,
) -> list[Packet]:
    """Build the packet sequence to upload one frame buffer."""
    if len(buffer) != spec.frame_bytes:
        raise ValidationError(
            f"Frame buffer is {len(buffer)} bytes but screen expects "
            f"{spec.frame_bytes} ({spec.width}x{spec.height} "
            f"{spec.pixel_format})."
        )
    return _make_screen_packets([buffer], spec=spec, delay_units=30, mode=2)


def upload_animation(
    frames: list[bytes],
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fps: int = 5,
) -> list[Packet]:
    """Build the packet sequence to upload a multi-frame animation."""
    if not frames:
        raise ValidationError("Animation has no frames.")
    for f in frames:
        if len(f) != spec.frame_bytes:
            raise ValidationError(
                f"Frame buffer is {len(f)} bytes but screen expects "
                f"{spec.frame_bytes}."
            )
            
    delay_ms = int(round(1000.0 / fps))
    delay_units = max(1, min(255, delay_ms // 2))
    return _make_screen_packets(frames, spec=spec, delay_units=delay_units, mode=3)


def set_display_mode(mode: int) -> list[Packet]:
    """Switch the on-screen display mode (clock face, custom image, etc.)."""
    p0 = Packet(0, raw_body=b"\x04\xf0", description="screen mode start")
    p1 = Packet(
        0,
        raw_body=bytes([0x04, 0xf5, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, mode & 0xFF]),
        description=f"screen mode {mode}",
    )
    p2 = Packet(0, raw_body=b"\x04\x02", description="screen mode commit")
    return [p0, p1, p2]
