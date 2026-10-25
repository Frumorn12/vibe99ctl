from __future__ import annotations

import shutil
import subprocess

import pytest
from PIL import Image

from vibe99.config import ScreenSpec
from vibe99.media.animation import _subsample, clip_from_animation, clip_from_video

SPEC = ScreenSpec(width=96, height=160)


def test_gif_keeps_its_frame_delays(tmp_path):
    path = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (40, 40), c) for c in ("red", "green", "blue")]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[50, 120, 300])
    clip = clip_from_animation(path, spec=SPEC)
    assert clip.delays_ms == [50, 120, 300]
    assert all(len(f) == SPEC.frame_bytes for f in clip.frames)


def test_subsample_merges_dropped_delays():
    images, delays = _subsample(list(range(10)), [10.0] * 10, 5)
    assert images == [0, 2, 4, 6, 8]
    assert delays == [20.0] * 5  # total duration is preserved


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_video_is_sampled_at_fps_from_start(tmp_path):
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=30:duration=4",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    clip = clip_from_video(path, spec=SPEC, fps=10, max_frames=12, start=1.0)
    assert len(clip.frames) == 12  # 1.2 s at 10 fps, not 12 frames spread over 4 s
    assert clip.delays_ms == [100.0] * 12
    assert all(len(f) == SPEC.frame_bytes for f in clip.frames)
