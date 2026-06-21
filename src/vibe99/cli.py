"""vibe99ctl command-line interface.

We use **Typer** (built on Click): type hints generate the parser, help and
shell-completion for free, sub-apps compose cleanly, and Rich gives readable
output. It keeps the command layer thin and declarative while the real work
lives in the device/protocol/media packages.
"""

from __future__ import annotations

from typing import Annotated

import typer

from . import __version__
from .commands import clock as clock_cmd
from .commands import diagnostics
from .commands import protocol as protocol_cmd
from .commands import rgb as rgb_cmd
from .commands import screen as screen_cmd
from .commands._shared import AppState, err
from .errors import Vibe99Error
from .logging_utils import configure

app = typer.Typer(
    name="vibe99",
    help=(
        "Open-source terminal driver for the Mechlands Vibe99 keyboard.\n\n"
        "Control RGB lighting, the integrated TFT screen, and the clock — no "
        "proprietary GUI required.\n\n"
        "[bold]Safety:[/] write commands run in DRY-RUN by default (the wire "
        "protocol is not yet hardware-verified). Add --apply to actually send."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=True,
)

# Sub-command groups.
app.add_typer(rgb_cmd.app, name="rgb")
app.add_typer(screen_cmd.app, name="screen")
app.add_typer(clock_cmd.app, name="clock")
app.add_typer(protocol_cmd.app, name="protocol")

# Top-level diagnostic commands.
app.command("info")(diagnostics.info)
app.command("list-devices")(diagnostics.list_devices)
app.command("dump-descriptor")(diagnostics.dump_descriptor)
app.command("doctor")(diagnostics.doctor)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"vibe99ctl {__version__}")
        raise typer.Exit()


def _parse_hex_int(value: str | None) -> int | None:
    # Accepts "0x3151" or bare hex like "3151" (base 16 understands both).
    if value is None:
        return None
    return int(value, 16)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        int, typer.Option("--verbose", "-v", count=True, help="-v info, -vv debug.")
    ] = 0,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Actually write to the device (default is dry-run)."),
    ] = False,
    vid: Annotated[str | None, typer.Option("--vid", help="Vendor ID in hex, e.g. 0x3151.")] = None,
    pid: Annotated[
        str | None, typer.Option("--pid", help="Product ID in hex, e.g. 0x4011.")
    ] = None,
    path: Annotated[
        str | None, typer.Option("--path", help="Exact HID path (from list-devices).")
    ] = None,
    _version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """Root callback: configure logging and stash global options."""
    configure(verbose)
    try:
        vid_int = _parse_hex_int(vid)
        pid_int = _parse_hex_int(pid)
    except ValueError as exc:
        err.print(f"[bold red]error:[/] invalid --vid/--pid (use hex like 0x3151): {exc}")
        raise typer.Exit(2) from exc

    ctx.obj = AppState(
        verbose=verbose,
        vid=vid_int,
        pid=pid_int,
        path=path.encode() if path else None,
        apply=apply,
    )


def run() -> None:
    """Console-script entry point with friendly top-level error handling."""
    try:
        app()
    except Vibe99Error as exc:
        err.print(f"[bold red]error:[/] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run()
