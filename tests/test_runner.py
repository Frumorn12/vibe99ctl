from __future__ import annotations

from vibe99.config import ScreenSpec
from vibe99.device.transport import DryRunTransport
from vibe99.protocol.screen import upload_frame
from vibe99.runner import send_packets


class AckingTransport(DryRunTransport):
    """Dry-run transport that answers screen chunks like the keyboard does."""

    def __init__(self, ack: bytes):
        super().__init__()
        self.ack = ack
        self.acks_read = 0

    def read_screen_ack(self, timeout_ms: int) -> bytes:
        self.acks_read += 1
        return self.ack


def _packets():
    spec = ScreenSpec(width=96, height=160)
    return upload_frame(b"\x00" * spec.frame_bytes, spec=spec)


def test_waits_for_an_ack_after_every_screen_chunk(monkeypatch):
    monkeypatch.setattr("vibe99.runner.time.sleep", lambda s: None)
    t = AckingTransport(b"\x01\x5a\x02" + b"\x00" * 61)
    seen = []
    result = send_packets(t, _packets(), progress=lambda done, total: seen.append((done, total)))
    assert t.acks_read == 8 == len(t.writes)
    assert result.missing_acks == 0
    assert seen[-1] == (11, 11)  # start + init + 8 chunks + commit


def test_counts_missing_acks(monkeypatch):
    monkeypatch.setattr("vibe99.runner.time.sleep", lambda s: None)
    result = send_packets(AckingTransport(b""), _packets())
    assert result.missing_acks == 8
