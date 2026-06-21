"""Media pipeline: convert images / GIFs / videos into device frame buffers."""

from __future__ import annotations

from .animation import frames_from_animation, frames_from_video, load_frame_sequence
from .image import image_to_frame, load_image_as_frame, to_rgb565

__all__ = [
    "frames_from_animation",
    "frames_from_video",
    "image_to_frame",
    "load_frame_sequence",
    "load_image_as_frame",
    "to_rgb565",
]
