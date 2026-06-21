"""Shared CLI state and helpers used by every sub-command.

The global options (``--vid``, ``--pid``, ``--path``, ``--apply``, ``-v``) are
parsed once in the root callback and stashed on ``ctx.obj`` as :class:`AppState`.
Helpers here turn that state into an open device + transport, and centralise how
write commands resolve dry-run vs. apply so behaviour is consistent everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer
from rich.console import Console

from ..device.discovery import DiscoveredDevice, open_device
from ..device.transport import DryRunTransport, Transport
from ..errors import Vibe99Error
from ..logging_utils import get_logger

log = get_logger("cli")

# stdout console (results); logging goes to stderr via logging_utils.
out = Console()
err = Console(stderr=True)


@dataclass
class AppState:
    verbose: int = 0
    vid: int | None = None
    pid: int | None = None
    path: bytes | None = None
    # apply=False => dry-run: build & show packets but never write to hardware.
    apply: bool = False


def get_state(ctx: typer.Context) -> AppState:
    if ctx.obj is None:
        ctx.obj = AppState()
    return ctx.obj


def open_target(state: AppState) -> tuple[DiscoveredDevice, Transport]:
    """Open the real device (used by read-only commands)."""
    return open_device(vid=state.vid, pid=state.pid, path=state.path)


def resolve_write_transport(
    state: AppState,
) -> tuple[DiscoveredDevice | None, Transport, bool]:
    """Return ``(device, transport, dry_run)`` for a write command.

    * With ``--apply`` we open the real device.
    * Without it (the safe default) we return a :class:`DryRunTransport` and try
      to identify the device for reporting, but never open it for writing.
    """
    if state.apply:
        device, transport = open_target(state)
        return device, transport, False

    # Dry-run: try to name the device, but don't fail if none is present.
    device: DiscoveredDevice | None = None
    try:
        device, real = open_target(state)
        real.close()
    except Vibe99Error:
        device = None
    return device, DryRunTransport(), True


def fail(message: str, code: int = 1) -> typer.Exit:
    """Print an error to stderr and return an Exit to raise."""
    err.print(f"[bold red]error:[/] {message}")
    return typer.Exit(code)


def print_dry_run_banner() -> None:
    err.print(
        "[yellow]dry-run[/] — no data written to the device. "
        "Re-run with [bold]--apply[/] to actually send."
    )
