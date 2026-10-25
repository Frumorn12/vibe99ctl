"""Transport abstraction over USB HID.

Two implementations are provided:

* :class:`HidTransport` — the real thing, backed by the ``hidapi`` library.
* :class:`DryRunTransport` — records everything that *would* be sent and never
  touches hardware. This is the default the CLI uses unless ``--apply`` is given,
  which is deliberate: the Vibe99 protocol is not yet confirmed, and we must not
  risk writing garbage to an unverified device.

Both implement the small :class:`Transport` Protocol so command builders never
care which one they're talking to.
"""

from __future__ import annotations

import contextlib
import sys
from typing import Protocol, runtime_checkable

from ..config import SCREEN_USAGE_PAGE, VIBE99_PID, VIBE99_VID
from ..errors import DeviceOpenError, TransportError
from ..logging_utils import get_logger

log = get_logger("transport")


@runtime_checkable
class Transport(Protocol):
    """Minimal interface the protocol layer depends on."""

    def write(self, data: bytes) -> int:
        """Send one output report. Returns the number of bytes written."""

    def read(self, size: int, timeout_ms: int | None = None) -> bytes:
        """Read one input report (may return ``b""`` on timeout)."""

    def get_feature_report(self, report_id: int, size: int) -> bytes: ...

    def read_screen_ack(self, timeout_ms: int) -> bytes:
        """Read the screen interface's per-chunk ACK (``b""`` on timeout)."""

    def send_feature_report(self, data: bytes) -> int: ...

    def close(self) -> None: ...


def _import_hid():
    """Import the optional ``hidapi`` bindings lazily with a helpful error.

    On Linux we prefer the ``hidraw`` backend that ships in the same wheel: it
    goes through ``/dev/hidraw*`` (so the udev rule grants access without root),
    reports the real product string and usage page even while the kernel binds
    the keyboard to the ``apple`` driver, and never detaches the kernel driver.
    The default ``hid`` module on Linux is the libusb backend, which sees
    neither and needs raw USB access.
    """
    if sys.platform.startswith("linux"):
        try:
            import hidraw  # type: ignore

            return hidraw
        except ImportError:  # pragma: no cover - environment dependent
            pass
    try:
        import hid  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DeviceOpenError(
            "The 'hidapi' package is not installed or failed to load. "
            "Install it with `pip install hidapi` (on Linux you also need "
            "libusb/libudev development headers)."
        ) from exc
    return hid


class HidTransport:
    """A real HID connection backed by ``hidapi``."""

    def __init__(self, path: bytes):
        hid = _import_hid()
        self._path = path
        self._dev = hid.device()
        self._screen_dev = None
        try:
            self._dev.open_path(path)
            self._dev.set_nonblocking(False)
        except OSError as exc:
            raise DeviceOpenError(
                f"Could not open HID device at {path!r}: {exc}. "
                "On Linux this is usually a udev permissions issue "
                "(see the README troubleshooting section)."
            ) from exc
        log.debug("Opened HID device at %r", path)

        # The pixel pipe is a sibling interface (usage page 0xFF68) of the same
        # keyboard; open it too so 4096-byte screen chunks can be routed there.
        try:
            for d in hid.enumerate(VIBE99_VID, VIBE99_PID):
                product = d.get("product_string") or ""
                is_screen = d.get("usage_page") == SCREEN_USAGE_PAGE
                if is_screen and (not product or "Vibe99" in product):
                    self._screen_dev = hid.device()
                    self._screen_dev.open_path(d["path"])
                    self._screen_dev.set_nonblocking(False)
                    log.debug("Opened sibling screen HID interface at %r", d["path"])
                    break
        except Exception as e:
            log.warning("Failed to auto-detect and open sibling screen interface: %s", e)

    def write(self, data: bytes) -> int:
        try:
            if len(data) == 4097 and self._screen_dev is not None:
                written = self._screen_dev.write(data)
            else:
                written = self._dev.write(data)
        except OSError as exc:
            raise TransportError(f"HID write failed: {exc}") from exc
        if written < 0:
            to_screen = len(data) == 4097 and self._screen_dev is not None
            dev_err = self._screen_dev.error() if to_screen else self._dev.error()
            raise TransportError(f"HID write returned -1 (device error: {dev_err}).")
        log.debug("WROTE %d bytes: %s", written, data.hex(" "))
        return written

    def read(self, size: int, timeout_ms: int | None = None) -> bytes:
        try:
            data = self._dev.read(size) if timeout_ms is None else self._dev.read(size, timeout_ms)
        except OSError as exc:
            raise TransportError(f"HID read failed: {exc}") from exc
        out = bytes(data)
        if out:
            log.debug("READ  %d bytes: %s", len(out), out.hex(" "))
        return out

    def read_screen_ack(self, timeout_ms: int) -> bytes:
        """Wait for the 64-byte ACK the screen interface sends after each chunk."""
        if self._screen_dev is None:
            return b""
        try:
            return bytes(self._screen_dev.read(64, timeout_ms))
        except OSError as exc:
            raise TransportError(f"HID read on the screen interface failed: {exc}") from exc

    def get_feature_report(self, report_id: int, size: int) -> bytes:
        try:
            data = self._dev.get_feature_report(report_id, size)
        except OSError as exc:
            raise TransportError(f"HID get_feature_report failed: {exc}") from exc
        return bytes(data)

    def send_feature_report(self, data: bytes) -> int:
        try:
            written = self._dev.send_feature_report(data)
        except OSError as exc:
            raise TransportError(f"HID send_feature_report failed: {exc}") from exc
        return written

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._dev.close()
        if self._screen_dev is not None:
            with contextlib.suppress(Exception):
                self._screen_dev.close()

    def __enter__(self) -> HidTransport:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class DryRunTransport:
    """A transport that records writes and never touches hardware.

    Useful as the safe default in the CLI and as a test double. Reads return
    queued canned responses (or empty bytes) so higher layers can be exercised.
    """

    def __init__(self, canned_reads: list[bytes] | None = None):
        self.writes: list[bytes] = []
        self.feature_writes: list[bytes] = []
        self._canned_reads: list[bytes] = list(canned_reads or [])

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        log.debug("[dry-run] WROTE %d bytes: %s", len(data), bytes(data).hex(" "))
        return len(data)

    def read(self, size: int, timeout_ms: int | None = None) -> bytes:
        if self._canned_reads:
            return self._canned_reads.pop(0)[:size]
        return b""

    def get_feature_report(self, report_id: int, size: int) -> bytes:
        if self._canned_reads:
            return self._canned_reads.pop(0)[:size]
        return b""

    def read_screen_ack(self, timeout_ms: int) -> bytes:
        return b""

    def send_feature_report(self, data: bytes) -> int:
        self.feature_writes.append(bytes(data))
        return len(data)

    def close(self) -> None:
        return None

    def __enter__(self) -> DryRunTransport:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
