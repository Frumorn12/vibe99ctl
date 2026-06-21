"""`vibe99 rgb ...` commands."""

from __future__ import annotations

from typing import Annotated

import typer

from ..protocol import rgb as rgb_proto
from ..runner import send_packets
from ..util.colors import RGB, available_names, parse_color
from ._shared import (
    fail,
    get_state,
    out,
    print_dry_run_banner,
    resolve_write_transport,
)

app = typer.Typer(no_args_is_help=True, help="Control the RGB backlight.")


def _run(ctx: typer.Context, packets, *, what: str) -> None:
    state = get_state(ctx)
    device, transport, dry_run = resolve_write_transport(state)
    try:
        result = send_packets(transport, packets, dry_run=dry_run)
    finally:
        transport.close()

    target = device.label if device else "(no device detected)"
    out.print(f"[green]{what}[/] -> {target}")
    if dry_run:
        for line in result.hex_dump:
            out.print(f"  [dim]{line}[/]")
        print_dry_run_banner()


@app.command("set")
def set_color(
    ctx: typer.Context,
    color: Annotated[str, typer.Argument(help="Color: '#RRGGBB', 'R,G,B', or a name.")],
    brightness: Annotated[int, typer.Option("--brightness", "-b", min=0, max=100)] = 100,
) -> None:
    """Set a solid static color across the whole keyboard."""
    try:
        rgb: RGB = parse_color(color)
    except Exception as exc:
        raise fail(str(exc)) from exc
    _run(
        ctx,
        [rgb_proto.set_solid_color(rgb, brightness=brightness)],
        what=f"rgb set {rgb} @ {brightness}%",
    )


@app.command("preset")
def preset(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Effect name.")],
    color: Annotated[str, typer.Option("--color", "-c", help="Base color (optional).")] = "",
    brightness: Annotated[int, typer.Option("--brightness", "-b", min=0, max=100)] = 100,
    speed: Annotated[int, typer.Option("--speed", "-s", min=0, max=100)] = 50,
) -> None:
    """Apply a lighting effect/preset (static, breathing, wave, rainbow, ...)."""
    key = name.lower()
    if key not in rgb_proto.PRESETS:
        raise fail(f"Unknown preset {name!r}. Available: {', '.join(rgb_proto.PRESETS)}")
    effect = rgb_proto.PRESETS[key]
    rgb = None
    if color:
        try:
            rgb = parse_color(color)
        except Exception as exc:
            raise fail(str(exc)) from exc
    _run(
        ctx,
        [rgb_proto.set_effect(effect, color=rgb, brightness=brightness, speed=speed)],
        what=f"rgb preset {key}",
    )


@app.command("brightness")
def brightness(
    ctx: typer.Context,
    value: Annotated[int, typer.Argument(min=0, max=100, help="Brightness 0-100.")],
) -> None:
    """Set only the global brightness."""
    _run(ctx, [rgb_proto.set_brightness(value)], what=f"rgb brightness {value}%")


@app.command("off")
def off(ctx: typer.Context) -> None:
    """Turn the backlight off."""
    _run(ctx, [rgb_proto.turn_off()], what="rgb off")


@app.command("presets")
def list_presets() -> None:
    """List available effects and color names."""
    out.print("[bold]Effects:[/] " + ", ".join(rgb_proto.PRESETS))
    out.print("[bold]Color names:[/] " + ", ".join(available_names()))
