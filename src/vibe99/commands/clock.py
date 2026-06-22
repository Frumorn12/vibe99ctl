"""`vibe99 clock ...` commands."""

from __future__ import annotations

import datetime as _dt
from typing import Annotated

import typer

from ..protocol import clock as clock_proto
from ..runner import send_packets
from ._shared import (
    fail,
    get_state,
    out,
    print_dry_run_banner,
    resolve_write_transport,
)

app = typer.Typer(no_args_is_help=True, help="Sync the on-screen clock.")


@app.command("sync")
def sync(
    ctx: typer.Context,
    at: Annotated[
        str,
        typer.Option(
            "--at", help="ISO datetime to send instead of now (e.g. 2026-06-21T13:45:00)."
        ),
    ] = "",
) -> None:
    """Push the current (or a given) date & time to the keyboard."""
    when = None
    if at:
        try:
            when = _dt.datetime.fromisoformat(at)
        except ValueError as exc:
            raise fail(f"Invalid --at value {at!r}: {exc}") from exc

    packets = clock_proto.sync(when)
    state = get_state(ctx)
    device, transport, dry_run = resolve_write_transport(state)
    try:
        result = send_packets(transport, packets, dry_run=dry_run)
    finally:
        transport.close()

    target = device.label if device else "(no device detected)"
    shown = (when or _dt.datetime.now()).isoformat(timespec="seconds")
    out.print(f"[green]clock sync[/] {shown} -> {target}")
    if dry_run:
        for line in result.hex_dump:
            out.print(f"  [dim]{line}[/]")
        print_dry_run_banner()
