"""Discovery: enumerate HID interfaces and match them against the catalog.

A keyboard typically exposes several HID interfaces (boot keyboard, NKRO,
consumer control, and one or more vendor-defined interfaces). The control
channel we want is the *vendor* interface, identified by its usage page. We pick
it heuristically and fall back gracefully so the tool still works if our usage
page guess is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import CONTROL_USAGE_PAGE, SCREEN_USAGE_PAGE
from ..errors import DeviceNotFoundError
from ..logging_utils import get_logger
from .descriptors import DeviceId, lookup
from .transport import HidTransport, Transport

log = get_logger("discovery")


@dataclass
class DiscoveredDevice:
    """One HID interface that matched (or might match) a Vibe99."""

    path: bytes
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    interface_number: int
    manufacturer: str
    product: str
    serial_number: str
    catalog: DeviceId | None  # None => not in our table

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    @property
    def is_vendor_interface(self) -> bool:
        return self.usage_page >= 0xFF00

    @property
    def label(self) -> str:
        name = self.catalog.name if self.catalog else (self.product or "Unknown device")
        return (
            f"{name} [{self.vid_pid}] iface={self.interface_number} "
            f"usage_page=0x{self.usage_page:04x}"
        )


def _enumerate_raw() -> list[dict]:
    """Wrapper around ``hid.enumerate`` that is easy to monkeypatch in tests."""
    try:
        import hid  # type: ignore
    except ImportError:  # pragma: no cover - environment dependent
        log.warning("hidapi not available; cannot enumerate HID devices.")
        return []
    return list(hid.enumerate())


def _to_discovered(entry: dict) -> DiscoveredDevice:
    vid = int(entry.get("vendor_id", 0))
    pid = int(entry.get("product_id", 0))
    product = str(entry.get("product_string") or "")
    return DiscoveredDevice(
        path=entry.get("path", b""),
        vendor_id=vid,
        product_id=pid,
        usage_page=int(entry.get("usage_page", 0)),
        usage=int(entry.get("usage", 0)),
        interface_number=int(entry.get("interface_number", -1)),
        manufacturer=str(entry.get("manufacturer_string") or ""),
        product=product,
        serial_number=str(entry.get("serial_number") or ""),
        catalog=lookup(vid, pid, product),
    )


def enumerate_all() -> list[DiscoveredDevice]:
    """Return every HID interface visible on the system."""
    return [_to_discovered(e) for e in _enumerate_raw()]


def find_devices(include_unknown: bool = False) -> list[DiscoveredDevice]:
    """Find candidate Vibe99 interfaces.

    :param include_unknown: when True, return *all* HID interfaces (useful for
        ``list-devices --all`` while hunting for the real VID/PID).
    """
    devices = enumerate_all()
    if include_unknown:
        return devices
    return [d for d in devices if d.catalog is not None]


def _rank(d: DiscoveredDevice) -> tuple:
    """Sort key: prefer cataloged, control-interface, higher-confidence entries."""
    confidence_rank = {"confirmed": 0, "probable": 1, "guess": 2}
    conf = confidence_rank.get(d.catalog.confidence, 3) if d.catalog else 4
    # The control channel (0xFF13) is the one we want for commands; rank it first,
    # then any vendor interface, then everything else.
    if d.usage_page == CONTROL_USAGE_PAGE:
        vendor_first = 0
    elif d.is_vendor_interface:
        vendor_first = 1
    else:
        vendor_first = 2
    return (conf, vendor_first, d.interface_number)


def find_screen_interface(
    devices: list[DiscoveredDevice] | None = None,
) -> DiscoveredDevice | None:
    """Find the screen/image upload interface (vendor usage page 0xFF68)."""
    candidates = devices if devices is not None else find_devices()
    for d in candidates:
        if d.usage_page == SCREEN_USAGE_PAGE:
            return d
    return None


def select_control_interface(
    devices: list[DiscoveredDevice],
) -> DiscoveredDevice | None:
    """Pick the most likely control interface from a list of candidates."""
    if not devices:
        return None
    return sorted(devices, key=_rank)[0]


def open_device(
    *,
    vid: int | None = None,
    pid: int | None = None,
    path: bytes | None = None,
) -> tuple[DiscoveredDevice, Transport]:
    """Locate and open the control interface of a Vibe99.

    Resolution order:
      1. explicit ``path`` (exact interface),
      2. explicit ``vid``/``pid`` filter,
      3. catalog auto-detection.

    :raises DeviceNotFoundError: if nothing suitable is found.
    """
    candidates = enumerate_all()

    if path is not None:
        chosen = next((d for d in candidates if d.path == path), None)
        if chosen is None:
            raise DeviceNotFoundError(f"No HID interface found at path {path!r}.")
    else:
        if vid is not None and pid is not None:
            candidates = [d for d in candidates if d.vendor_id == vid and d.product_id == pid]
        else:
            candidates = [d for d in candidates if d.catalog is not None]
        chosen = select_control_interface(candidates)

    if chosen is None:
        raise DeviceNotFoundError(
            "No Mechlands Vibe99 (or compatible) device found. "
            "Make sure the keyboard is connected in WIRED mode, then run "
            "`vibe99 list-devices --all` to find its VID/PID and report it."
        )

    log.info("Selected control interface: %s", chosen.label)
    transport = HidTransport(chosen.path)
    return chosen, transport
