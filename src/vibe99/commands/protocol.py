"""`vibe99 protocol ...` — helpers for the reverse-engineering effort."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel

from ..errors import Vibe99Error
from ..protocol.packets import Opcode, Packet, checksum_sum8, checksum_xor, crc16_ccitt
from ..runner import send_packets
from ._shared import fail, get_state, out, resolve_write_transport

app = typer.Typer(no_args_is_help=True, help="Reverse-engineering helpers.")

_SNIFF_NOTES = """\
[bold]How to capture the Vibe99 protocol[/]

The official driver is a Windows app, but devices in this OEM family also ship a
WebHID web driver. WebHID is the easiest capture path because it's plain JS.

[bold]Path A — WebHID console hook (easiest)[/]
1. Open the vendor web driver in Chrome/Edge and connect the keyboard (wired).
2. DevTools > Console, then install a hook before you click anything:

   const _orig = HIDDevice.prototype.sendReport;
   HIDDevice.prototype.sendReport = function (id, data) {
     console.log('TX', id, [...new Uint8Array(data.buffer ?? data)]
       .map(b => b.toString(16).padStart(2,'0')).join(' '));
     return _orig.call(this, id, data);
   };

3. Trigger ONE action at a time (set red, upload image, sync clock) and copy the
   logged bytes. One isolated action per capture = far easier to decode.

[bold]Path B — USB sniff (Wireshark + usbmon / USBPcap)[/]
  Linux:  sudo modprobe usbmon ; wireshark -> usbmonX
  Windows: install USBPcap, capture in Wireshark.
  Filter to the keyboard's bus/device, then run one action at a time.

[bold]What to record for each action[/]
  - Report ID (first byte) and total report length.
  - The opcode byte and where it sits.
  - Which bytes change when you change ONE parameter (color, brightness, frame).
  - The last byte(s): try sum8 / xor / crc16 to find the checksum
    (use `vibe99 protocol checksum <hexbytes>`).

Paste findings into [bold]docs/protocol.md[/] and open a PR / issue with the
[italic]protocol[/] label. See docs/reverse-engineering.md for the full guide.
"""


@app.command("sniff-notes")
def sniff_notes() -> None:
    """Print a concise, actionable guide for capturing the protocol."""
    out.print(Panel.fit(_SNIFF_NOTES, border_style="cyan"))


@app.command("checksum")
def checksum(
    hexbytes: Annotated[str, typer.Argument(help="Bytes as hex, e.g. '06 01 64 ff'.")],
) -> None:
    """Compute candidate checksums over the given bytes (to match a capture)."""
    cleaned = hexbytes.replace(",", " ").replace("0x", " ")
    try:
        data = bytes(int(tok, 16) for tok in cleaned.split())
    except ValueError as exc:
        raise fail(f"Could not parse hex bytes: {exc}") from exc
    out.print(f"input ({len(data)} bytes): {data.hex(' ')}")
    out.print(f"  sum8       : 0x{checksum_sum8(data):02x}")
    out.print(f"  xor8       : 0x{checksum_xor(data):02x}")
    out.print(f"  crc16-ccitt: 0x{crc16_ccitt(data):04x}")


@app.command("ping")
def ping(ctx: typer.Context) -> None:
    """Send a device-info/ping request and print any response.

    Honors the global --apply flag. In dry-run it just shows the request bytes.
    """
    state = get_state(ctx)
    request = Packet(Opcode.DEVICE_INFO, b"", description="device-info request")

    _device, transport, dry_run = resolve_write_transport(state)
    try:
        send_packets(transport, [request], dry_run=dry_run)
        out.print(f"[bold]request[/]: {request.hex()}")
        if dry_run:
            out.print("[yellow]dry-run[/] — re-run with --apply to read a real response.")
            return
        response = transport.read(64, timeout_ms=1000)
        if response:
            out.print(f"[green]response[/] ({len(response)} bytes): {response.hex(' ')}")
        else:
            out.print("[yellow]no response[/] (timeout). The opcode is a guess (# TO-VERIFY).")
    except Vibe99Error as exc:
        raise fail(str(exc)) from exc
    finally:
        transport.close()
