"""Read-only diagnostic commands: info, list-devices, dump-descriptor, doctor.

These never write to the device, so they always run for real (no dry-run gate).
"""

from __future__ import annotations

import platform
import sys
from typing import Annotated

import typer
from rich.table import Table

from .. import __version__
from ..config import DEFAULT_SCREEN, HID_REPORT_SIZE, VENDOR_USAGE_PAGE
from ..device.descriptors import catalog_stats
from ..device.discovery import enumerate_all, find_devices, open_device
from ..errors import Vibe99Error
from ._shared import get_state, out


def _confidence_color(conf: str) -> str:
    return {"confirmed": "green", "probable": "yellow", "guess": "red"}.get(conf, "white")


def info(ctx: typer.Context) -> None:
    """Show tool, screen and detected-device information."""
    state = get_state(ctx)

    out.print(f"[bold]vibe99ctl[/] v{__version__}")
    out.print(
        f"screen model: {DEFAULT_SCREEN.width}x{DEFAULT_SCREEN.height} "
        f"{DEFAULT_SCREEN.pixel_format} "
        f"({DEFAULT_SCREEN.frame_bytes} bytes/frame)  [dim](probable)[/]"
    )

    try:
        device, transport = open_device(vid=state.vid, pid=state.pid, path=state.path)
        transport.close()
        out.print(f"[green]detected:[/] {device.label}")
        if device.catalog:
            color = _confidence_color(device.catalog.confidence)
            out.print(f"  match confidence: [{color}]{device.catalog.confidence}[/]")
    except Vibe99Error as exc:
        out.print(f"[yellow]no device:[/] {exc}")


def list_devices(
    ctx: typer.Context,
    show_all: Annotated[
        bool, typer.Option("--all", "-a", help="List every HID interface.")
    ] = False,
) -> None:
    """List detected Vibe99 (or, with --all, every HID device)."""
    devices = find_devices(include_unknown=show_all)
    if not devices:
        out.print("[yellow]No matching devices found.[/]")
        out.print("Tip: connect the keyboard in WIRED mode and try `--all`.")
        return

    table = Table(title="HID devices" if show_all else "Vibe99 candidates")
    table.add_column("VID:PID")
    table.add_column("iface", justify="right")
    table.add_column("usage_page")
    table.add_column("product")
    table.add_column("known", justify="center")

    for d in sorted(devices, key=lambda x: (x.vid_pid, x.interface_number)):
        known = ""
        if d.catalog:
            color = _confidence_color(d.catalog.confidence)
            known = f"[{color}]{d.catalog.confidence}[/]"
        vendor_mark = " *" if d.usage_page == VENDOR_USAGE_PAGE else ""
        table.add_row(
            d.vid_pid,
            str(d.interface_number),
            f"0x{d.usage_page:04x}{vendor_mark}",
            d.product or d.manufacturer or "-",
            known,
        )
    out.print(table)
    out.print("[dim]* = vendor usage page (most likely control interface)[/]")


def dump_descriptor(
    ctx: typer.Context,
    show_all: Annotated[
        bool, typer.Option("--all", "-a", help="Dump every HID interface.")
    ] = False,
) -> None:
    """Dump raw HID enumeration details (for reverse-engineering reports)."""
    devices = enumerate_all()
    if not show_all:
        devices = [d for d in devices if d.catalog is not None]
    if not devices:
        out.print("[yellow]Nothing to dump.[/] Try `--all`.")
        return
    for d in devices:
        out.print(f"[bold]{d.vid_pid}[/]  iface={d.interface_number}")
        out.print(f"  manufacturer : {d.manufacturer!r}")
        out.print(f"  product      : {d.product!r}")
        out.print(f"  serial       : {d.serial_number!r}")
        out.print(f"  usage_page   : 0x{d.usage_page:04x}")
        out.print(f"  usage        : 0x{d.usage:04x}")
        out.print(f"  path         : {d.path!r}")
        out.print(f"  in catalog   : {bool(d.catalog)}")
        out.print("")


def doctor(ctx: typer.Context) -> None:
    """Run environment & connectivity checks and print actionable hints."""
    ok = "[green]OK[/]"
    warn = "[yellow]WARN[/]"
    bad = "[red]FAIL[/]"

    out.print("[bold]vibe99 doctor[/]\n")

    # 1. Python.
    out.print(f"{ok}  Python {platform.python_version()} ({sys.platform})")

    # 2. hidapi import.
    try:
        import hid  # type: ignore  # noqa: F401

        out.print(f"{ok}  hidapi import")
    except Exception as exc:
        out.print(f"{bad}  hidapi import: {exc}")
        out.print("      -> pip install hidapi (Linux also needs libudev/libusb headers)")

    # 3. Pillow.
    try:
        import PIL  # type: ignore

        out.print(f"{ok}  Pillow {PIL.__version__}")
    except Exception as exc:
        out.print(f"{bad}  Pillow: {exc}")

    # 4. Optional media backends.
    media = []
    try:
        import imageio  # type: ignore  # noqa: F401

        media.append("imageio")
    except ImportError:
        pass
    try:
        import cv2  # type: ignore  # noqa: F401

        media.append("opencv")
    except ImportError:
        pass
    if media:
        out.print(f"{ok}  video backend(s): {', '.join(media)}")
    else:
        out.print(
            f"{warn}  no video backend (GIF still works). "
            r"Install 'vibe99ctl\[media]' for video."
        )

    # 5. Catalog.
    stats = catalog_stats()
    out.print(
        f"{warn}  device catalog: {stats.confirmed} confirmed / "
        f"{stats.probable} probable / {stats.guess} guess "
        f"(protocol not yet hardware-verified)"
    )

    # 6. Enumeration / detection.
    try:
        all_hid = enumerate_all()
        out.print(f"{ok}  HID enumeration: {len(all_hid)} interface(s) visible")
    except Exception as exc:
        out.print(f"{bad}  HID enumeration failed: {exc}")
        all_hid = []

    matches = [d for d in all_hid if d.catalog is not None]
    if matches:
        out.print(f"{ok}  Vibe99 candidate(s): {len(matches)}")
        for d in matches:
            out.print(f"      - {d.label}")
    else:
        out.print(f"{warn}  no Vibe99 candidate detected")
        out.print("      -> connect in WIRED mode; run `vibe99 list-devices --all`")

    # 7. Linux permissions hint.
    if sys.platform.startswith("linux"):
        out.print(f"{warn}  Linux: if open fails with 'access denied', install the udev rule")
        out.print("      (see README → Troubleshooting).")

    out.print(
        f"\nReport size model: {HID_REPORT_SIZE} bytes, "
        f"vendor usage page: 0x{VENDOR_USAGE_PAGE:04x}  [dim](both to-verify)[/]"
    )
