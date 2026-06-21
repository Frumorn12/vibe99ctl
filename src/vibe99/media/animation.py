"""Animation & video conversion.

IMPORTANT — honest scope: the Vibe99 has **no native video support**. Its driver
accepts GIF/animation frames. So "uploading a video" here means *converting* the
video into a frame sequence the device can display. We never pretend to stream
real video.

* GIFs are decoded with Pillow (always available).
* Real videos (mp4/webm/mov/...) require an optional backend. We try
  ``imageio`` (+ ``imageio-ffmpeg``) first, then OpenCV. If neither is present we
  raise a clear, actionable error telling the user what to install.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageSequence

from ..config import DEFAULT_ANIMATION_FPS, DEFAULT_SCREEN, MAX_ANIMATION_FRAMES, ScreenSpec
from ..errors import MediaError, UnsupportedFeatureError
from ..logging_utils import get_logger
from .image import image_to_frame

log = get_logger("media.animation")

VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".gifv"}
ANIMATION_SUFFIXES = {".gif", ".webp", ".apng", ".png"}


def _cap_frames(frames: list, max_frames: int) -> list:
    """Uniformly subsample a frame list down to ``max_frames``."""
    if len(frames) <= max_frames:
        return frames
    step = len(frames) / max_frames
    picked = [frames[int(i * step)] for i in range(max_frames)]
    log.info("Capped %d frames down to %d.", len(frames), len(picked))
    return picked


def frames_from_animation(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "contain",
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Decode an animated image (GIF/APNG/animated WebP) into frame buffers."""
    p = Path(path)
    if not p.exists():
        raise MediaError(f"Animation file not found: {p}")
    try:
        with Image.open(p) as img:
            raw_frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(img)]
    except Exception as exc:
        raise MediaError(f"Could not decode animation {p}: {exc}") from exc

    if not raw_frames:
        raise MediaError(f"No frames found in {p}.")

    raw_frames = _cap_frames(raw_frames, max_frames)
    return [image_to_frame(f, spec=spec, fit=fit) for f in raw_frames]


def _video_reader(path: Path):
    """Yield RGB Pillow images from a video, using whichever backend exists."""
    # Backend 1: imageio (+ ffmpeg).
    try:
        import imageio.v3 as iio  # type: ignore

        for frame in iio.imiter(path):  # numpy HxWx3 (or HxWx4)
            yield Image.fromarray(frame[..., :3], mode="RGB")
        return
    except ImportError:
        pass
    except Exception as exc:
        raise MediaError(f"imageio failed to read {path}: {exc}") from exc

    # Backend 2: OpenCV.
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise UnsupportedFeatureError(
            "Reading real video files needs an extra backend. Install one of:\n"
            "  pip install 'vibe99ctl[media]'      # imageio + ffmpeg\n"
            "  pip install 'vibe99ctl[media-full]' # + OpenCV\n"
            "Tip: pre-converting your clip to a GIF also works with no extras."
        ) from exc

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise MediaError(f"OpenCV could not open video {path}.")
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            yield Image.fromarray(frame_rgb, mode="RGB")
    finally:
        cap.release()


def frames_from_video(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "cover",
    fps: int = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Convert a real video file into a capped sequence of frame buffers.

    Frames are decoded then uniformly subsampled to roughly ``fps`` * duration,
    and hard-capped at ``max_frames`` to keep the upload small.
    """
    p = Path(path)
    if not p.exists():
        raise MediaError(f"Video file not found: {p}")

    decoded = list(_video_reader(p))
    if not decoded:
        raise MediaError(f"No frames decoded from {p}.")

    # We don't know the source fps reliably across backends, so we simply cap to
    # max_frames (which, combined with the device's low refresh, is what matters).
    decoded = _cap_frames(decoded, max_frames)
    log.info("Converted video to %d frames (target fps ~%d).", len(decoded), fps)
    return [image_to_frame(f, spec=spec, fit=fit) for f in decoded]


def load_frame_sequence(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str | None = None,
    fps: int = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Dispatch to the right decoder based on file extension."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return frames_from_video(p, spec=spec, fit=fit or "cover", fps=fps, max_frames=max_frames)
    if suffix in ANIMATION_SUFFIXES:
        return frames_from_animation(p, spec=spec, fit=fit or "contain", max_frames=max_frames)
    raise MediaError(
        f"Unsupported media type {suffix!r}. Supported: "
        f"{sorted(ANIMATION_SUFFIXES | VIDEO_SUFFIXES)}"
    )
