"""Animation & video conversion.

IMPORTANT — honest scope: the Vibe99 has **no native video support**. It stores
up to 255 frames, each with its own delay, and loops them. So "uploading a
video" here means *converting* a stretch of the video into such a frame
sequence. We never pretend to stream real video.

* GIF / APNG / animated WebP are decoded with Pillow, keeping each frame's delay.
* Real videos (mp4/webm/mov/...) are decoded by ``ffmpeg`` (the system one, or
  the binary bundled with ``imageio-ffmpeg``), which streams only the frames we
  keep: a long video costs no more memory than a short one.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

from ..config import DEFAULT_ANIMATION_FPS, DEFAULT_SCREEN, MAX_ANIMATION_FRAMES, ScreenSpec
from ..errors import MediaError, UnsupportedFeatureError
from ..logging_utils import get_logger
from .image import image_to_frame

log = get_logger("media.animation")

VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".gifv"}
ANIMATION_SUFFIXES = {".gif", ".webp", ".apng", ".png"}
DEFAULT_GIF_DELAY_MS = 100  # what browsers use when a GIF frame has no delay


@dataclass
class Clip:
    """A frame sequence ready for upload: device frame buffers + per-frame delays."""

    frames: list[bytes]
    delays_ms: list[float]

    @property
    def duration_ms(self) -> float:
        return sum(self.delays_ms)


def _on_black(frame: Image.Image) -> Image.Image:
    """Flatten a (possibly transparent) frame onto black, like the screen shows it."""
    rgba = frame.convert("RGBA")
    bg = Image.new("RGB", rgba.size, (0, 0, 0))
    bg.paste(rgba, mask=rgba.getchannel("A"))
    return bg


def _subsample(images: list, delays: list[float], max_frames: int) -> tuple[list, list[float]]:
    """Keep ``max_frames`` evenly spaced frames, merging the delays of dropped ones."""
    if len(images) <= max_frames:
        return images, delays
    step = len(images) / max_frames
    picked, merged = [], []
    for i in range(max_frames):
        a, b = int(i * step), int((i + 1) * step)
        picked.append(images[a])
        merged.append(sum(delays[a:b]))
    log.info("Capped %d frames down to %d.", len(images), len(picked))
    return picked, merged


def clip_from_animation(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "contain",
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> Clip:
    """Decode an animated image (GIF/APNG/animated WebP), keeping its timing."""
    p = Path(path)
    if not p.exists():
        raise MediaError(f"Animation file not found: {p}")
    try:
        with Image.open(p) as img:
            images, delays = [], []
            for frame in ImageSequence.Iterator(img):
                images.append(_on_black(frame))
                delays.append(float(frame.info.get("duration") or DEFAULT_GIF_DELAY_MS))
    except Exception as exc:
        raise MediaError(f"Could not decode animation {p}: {exc}") from exc
    if not images:
        raise MediaError(f"No frames found in {p}.")

    images, delays = _subsample(images, delays, max_frames)
    return Clip([image_to_frame(f, spec=spec, fit=fit) for f in images], delays)


def ffmpeg_exe() -> str:
    """Path of an ffmpeg binary, or a clear error saying how to get one."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise UnsupportedFeatureError(
            "Reading real video files needs ffmpeg. Install it with your package\n"
            "manager, or: pip install 'vibe99ctl[media]'  (bundles an ffmpeg binary).\n"
            "Tip: pre-converting your clip to a GIF also works with no extras."
        ) from exc


def _fit_filter(spec: ScreenSpec, fit: str) -> str:
    w, h = spec.width, spec.height
    if fit == "cover":
        return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    if fit == "contain":
        return (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )
    if fit == "stretch":
        return f"scale={w}:{h}:flags=lanczos"
    raise MediaError(f"Unknown fit mode {fit!r}. Use stretch|contain|cover.")


def video_frames_rgb(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "cover",
    fps: float = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
    start: float = 0.0,
) -> list[Image.Image]:
    """Decode up to ``max_frames`` frames at ``fps``, starting at ``start`` seconds.

    ffmpeg resamples to ``fps`` and fits the picture to the screen, so we only
    ever hold ``max_frames`` tiny frames in memory.
    """
    p = Path(path)
    if not p.exists():
        raise MediaError(f"Video file not found: {p}")
    cmd = [
        ffmpeg_exe(),
        "-v",
        "error",
        "-nostdin",
        "-ss",
        f"{max(0.0, start):.3f}",
        "-i",
        str(p),
        "-an",
        "-vf",
        f"fps={fps},{_fit_filter(spec, fit)}",
        "-frames:v",
        str(max_frames),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    log.debug("Running %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, check=False)
    frame_size = spec.width * spec.height * 3
    raw = proc.stdout
    if proc.returncode != 0 or len(raw) < frame_size:
        detail = proc.stderr.decode(errors="replace").strip().splitlines()
        raise MediaError(
            f"ffmpeg could not decode {p.name}"
            + (f": {detail[-1]}" if detail else " (no frames at that start time?)")
        )
    return [
        Image.frombytes("RGB", (spec.width, spec.height), raw[i : i + frame_size])
        for i in range(0, len(raw) - frame_size + 1, frame_size)
    ]


def clip_from_video(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "cover",
    fps: float = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
    start: float = 0.0,
) -> Clip:
    """Convert ``max_frames / fps`` seconds of a video, from ``start``, into a clip."""
    images = video_frames_rgb(path, spec=spec, fit=fit, fps=fps, max_frames=max_frames, start=start)
    log.info("Converted video to %d frames at %g fps.", len(images), fps)
    # Already fitted by ffmpeg: "stretch" is a no-op resize here.
    frames = [image_to_frame(f, spec=spec, fit="stretch") for f in images]
    return Clip(frames, [1000.0 / fps] * len(frames))


def load_clip(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str | None = None,
    fps: float = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
    start: float = 0.0,
) -> Clip:
    """Dispatch to the right decoder based on file extension."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return clip_from_video(
            p, spec=spec, fit=fit or "cover", fps=fps, max_frames=max_frames, start=start
        )
    if suffix in ANIMATION_SUFFIXES:
        return clip_from_animation(p, spec=spec, fit=fit or "contain", max_frames=max_frames)
    raise MediaError(
        f"Unsupported media type {suffix!r}. Supported: "
        f"{sorted(ANIMATION_SUFFIXES | VIDEO_SUFFIXES)}"
    )


# --------------------------------------------------------------------------- #
# Frame-only helpers (kept for library users; they drop the timing)
# --------------------------------------------------------------------------- #
def frames_from_animation(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "contain",
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Decode an animated image (GIF/APNG/animated WebP) into frame buffers."""
    return clip_from_animation(path, spec=spec, fit=fit, max_frames=max_frames).frames


def frames_from_video(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str = "cover",
    fps: int = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Convert the start of a video into frame buffers sampled at ``fps``."""
    return clip_from_video(path, spec=spec, fit=fit, fps=fps, max_frames=max_frames).frames


def load_frame_sequence(
    path: str | Path,
    *,
    spec: ScreenSpec = DEFAULT_SCREEN,
    fit: str | None = None,
    fps: int = DEFAULT_ANIMATION_FPS,
    max_frames: int = MAX_ANIMATION_FRAMES,
) -> list[bytes]:
    """Frame buffers of any supported animation or video (see :func:`load_clip`)."""
    return load_clip(path, spec=spec, fit=fit, fps=fps, max_frames=max_frames).frames
