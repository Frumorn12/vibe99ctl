"""Image loading and conversion to the device's framebuffer format.

Everything funnels through Pillow. The output is a flat ``bytes`` buffer of
``spec.frame_bytes`` length, ready for :func:`vibe99.protocol.screen.upload_frame`.
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageOps

from ..config import DEFAULT_SCREEN, ScreenSpec
from ..errors import MediaError

# Pre-built little/big endian struct packers for speed on large buffers.
_PACK_LE = struct.Struct("<H").pack
_PACK_BE = struct.Struct(">H").pack


def to_rgb565(image: Image.Image, *, little_endian: bool = True) -> bytes:
    """Convert an RGB Pillow image to a packed RGB565 byte buffer."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    raw = image.tobytes()  # tightly packed RGB, 3 bytes per pixel
    try:
        import numpy as np  # comes with the [media] extra; ~100x faster
    except ImportError:
        np = None
    if np is not None:
        px = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.uint16)
        value = ((px[:, 0] & 0xF8) << 8) | ((px[:, 1] & 0xFC) << 3) | (px[:, 2] >> 3)
        return value.astype("<u2" if little_endian else ">u2").tobytes()
    pack = _PACK_LE if little_endian else _PACK_BE
    out = bytearray()
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out += pack(value)
    return bytes(out)


def _fit(image: Image.Image, spec: ScreenSpec, *, fit: str) -> Image.Image:
    """Resize ``image`` to the screen size using the chosen strategy."""
    target = (spec.width, spec.height)
    if fit == "stretch":
        return image.resize(target, Image.Resampling.LANCZOS)
    if fit == "contain":
        # Letterbox: preserve aspect ratio, pad with black.
        return ImageOps.pad(image, target, color=(0, 0, 0), method=Image.Resampling.LANCZOS)
    if fit == "cover":
        # Crop to fill: preserve aspect ratio, center-crop the overflow.
        return ImageOps.fit(image, target, method=Image.Resampling.LANCZOS)
    raise MediaError(f"Unknown fit mode {fit!r}. Use stretch|contain|cover.")


def image_to_frame(
    image: Image.Image,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "contain",
) -> bytes:
    """Convert any Pillow image into a device frame buffer."""
    fitted = _fit(image, spec, fit=fit)
    little_endian = spec.pixel_format.endswith("-le")
    if spec.pixel_format.startswith("rgb565"):
        return to_rgb565(fitted, little_endian=little_endian)
    if spec.pixel_format == "rgb888":
        return fitted.convert("RGB").tobytes()
    raise MediaError(f"Unsupported pixel format {spec.pixel_format!r}.")


def load_image_as_frame(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "contain",
) -> bytes:
    """Load an image file and convert it to a device frame buffer."""
    p = Path(path)
    if not p.exists():
        raise MediaError(f"Image file not found: {p}")
    try:
        with Image.open(p) as img:
            img.load()
            return image_to_frame(img, spec=spec, fit=fit)
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError(f"Could not load image {p}: {exc}") from exc
