"""`vibe99 screen ...` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..config import DEFAULT_ANIMATION_FPS, DEFAULT_SCREEN, MAX_ANIMATION_FRAMES, ScreenSpec
from ..errors import Vibe99Error
from ..media import load_image_as_frame
from ..media.animation import frames_from_video, load_frame_sequence
from ..protocol import screen as screen_proto
from ..runner import send_packets
from ._shared import (
    fail,
    get_state,
    out,
    print_dry_run_banner,
    resolve_write_transport,
)

app = typer.Typer(no_args_is_help=True, help="Control the integrated TFT screen.")

FitOption = Annotated[str, typer.Option("--fit", help="contain | cover | stretch")]


def _spec(width: int | None, height: int | None) -> ScreenSpec:
    if width is None and height is None:
        return DEFAULT_SCREEN
    return ScreenSpec(
        width=width or DEFAULT_SCREEN.width,
        height=height or DEFAULT_SCREEN.height,
        pixel_format=DEFAULT_SCREEN.pixel_format,
    )


def _send(ctx: typer.Context, packets, *, what: str, frames: int) -> None:
    state = get_state(ctx)
    device, transport, dry_run = resolve_write_transport(state)
    try:
        result = send_packets(transport, packets, dry_run=dry_run)
    finally:
        transport.close()

    target = device.label if device else "(no device detected)"
    out.print(
        f"[green]{what}[/] -> {target}  "
        f"({frames} frame(s), {result.packets_sent} packets, {result.bytes_sent} bytes)"
    )
    if dry_run:
        # A full frame is hundreds of chunks; show only the framing packets.
        head = [ln for ln in result.hex_dump if "data chunk" not in ln][:6]
        for line in head:
            out.print(f"  [dim]{line}[/]")
        if result.packets_sent > len(head):
            out.print(f"  [dim]... (+{result.packets_sent - len(head)} data chunks)[/]")
        print_dry_run_banner()


@app.command("upload-image")
def upload_image(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Image file.")],
    fit: FitOption = "contain",
    width: Annotated[int | None, typer.Option("--width", help="Override screen width.")] = None,
    height: Annotated[int | None, typer.Option("--height", help="Override screen height.")] = None,
) -> None:
    """Upload a single static image to the screen."""
    spec = _spec(width, height)
    try:
        frame = load_image_as_frame(path, spec=spec, fit=fit)
        packets = screen_proto.upload_frame(frame, spec=spec)
    except Vibe99Error as exc:
        raise fail(str(exc)) from exc
    _send(ctx, packets, what=f"screen upload-image {path.name}", frames=1)


@app.command("upload-animation")
def upload_animation(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="GIF/APNG/WebP.")],
    fit: FitOption = "contain",
    fps: Annotated[int, typer.Option("--fps", min=1, max=30)] = DEFAULT_ANIMATION_FPS,
    max_frames: Annotated[int, typer.Option("--max-frames", min=1)] = MAX_ANIMATION_FRAMES,
    width: Annotated[int | None, typer.Option("--width")] = None,
    height: Annotated[int | None, typer.Option("--height")] = None,
) -> None:
    """Upload an animated GIF (or APNG/animated WebP) to the screen."""
    spec = _spec(width, height)
    try:
        frames = load_frame_sequence(path, spec=spec, fit=fit, fps=fps, max_frames=max_frames)
        packets = screen_proto.upload_animation(frames, spec=spec, fps=fps)
    except Vibe99Error as exc:
        raise fail(str(exc)) from exc
    _send(ctx, packets, what=f"screen upload-animation {path.name}", frames=len(frames))


@app.command("upload-video")
def upload_video(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Video file.")],
    fit: FitOption = "cover",
    fps: Annotated[int, typer.Option("--fps", min=1, max=30)] = DEFAULT_ANIMATION_FPS,
    max_frames: Annotated[int, typer.Option("--max-frames", min=1)] = MAX_ANIMATION_FRAMES,
    width: Annotated[int | None, typer.Option("--width")] = None,
    height: Annotated[int | None, typer.Option("--height")] = None,
) -> None:
    """Convert a video into an on-device animation and upload it.

    NOTE: the Vibe99 does NOT play real video. This command decodes the video,
    downsamples it to a handful of frames, and uploads it as an animation. The
    result is a choppy, looping clip — that's a hardware limit, not a bug.
    """
    spec = _spec(width, height)
    try:
        frames = frames_from_video(path, spec=spec, fit=fit, fps=fps, max_frames=max_frames)
        packets = screen_proto.upload_animation(frames, spec=spec, fps=fps)
    except Vibe99Error as exc:
        raise fail(str(exc)) from exc
    _send(ctx, packets, what=f"screen upload-video {path.name}", frames=len(frames))


@app.command("mode")
def mode(
    ctx: typer.Context,
    value: Annotated[int, typer.Argument(min=0, max=255, help="Display mode index.")],
) -> None:
    """Switch the on-screen display mode (clock face / custom image / ...)."""
    _send(ctx, screen_proto.set_display_mode(value), what=f"screen mode {value}", frames=0)
