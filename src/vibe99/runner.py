"""Send sequences of packets over a transport.

This is the single choke point where packets become wire bytes. It handles the
inter-chunk pacing and produces a tidy report of what happened — including, in
dry-run mode, a full hex dump so users (and the reverse-engineering effort) can
inspect exactly what *would* have been sent.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .config import INTER_CHUNK_DELAY_S
from .device.transport import Transport
from .logging_utils import get_logger
from .protocol.packets import Packet

log = get_logger("runner")


@dataclass
class SendResult:
    packets_sent: int = 0
    bytes_sent: int = 0
    hex_dump: list[str] = field(default_factory=list)
    dry_run: bool = False


def send_packets(
    transport: Transport,
    packets: Sequence[Packet] | Iterable[Packet],
    *,
    dry_run: bool = False,
    delay_s: float = INTER_CHUNK_DELAY_S,
    collect_hex: bool = False,
) -> SendResult:
    """Send a sequence of packets.

    :param dry_run: when True, never call ``transport.write`` — only record.
    :param collect_hex: when True (or in dry-run), keep a hex dump per packet.
    """
    result = SendResult(dry_run=dry_run)
    keep_hex = collect_hex or dry_run

    for pkt in packets:
        report = pkt.to_report()
        if keep_hex:
            label = pkt.description or f"opcode=0x{pkt.opcode:02x}"
            result.hex_dump.append(f"{label}: {report.hex(' ')}")
        if dry_run:
            log.debug("[dry-run] %s", pkt.description)
        else:
            if pkt.report_size == 64:
                transport.send_feature_report(report)
                try:
                    transport.get_feature_report(0, 65)
                except Exception as exc:
                    log.warning("Feature report readback handshake failed: %s", exc)
                if "screen upload" in (pkt.description or ""):
                    time.sleep(0.2)  # Give the device time to process setup/init commands
                elif delay_s:
                    time.sleep(delay_s)
            else:
                transport.write(report)
                if delay_s:
                    time.sleep(delay_s)
        result.packets_sent += 1
        result.bytes_sent += len(report)

    log.info(
        "%s %d packet(s), %d bytes.",
        "Would send" if dry_run else "Sent",
        result.packets_sent,
        result.bytes_sent,
    )
    return result
