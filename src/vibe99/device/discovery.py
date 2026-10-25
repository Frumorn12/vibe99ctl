"""Discovery: enumerate HID interfaces and match them against the catalog.

A keyboard typically exposes several HID interfaces (boot keyboard, NKRO,
consumer control, and one or more vendor-defined interfaces). The control
channel we want is the *vendor* interface, identified by its usage page. We pick
it heuristically and fall back gracefully so the tool still works if our usage
page guess is wrong.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import CONTROL_USAGE_PAGE, SCREEN_USAGE_PAGE
from ..errors import DeviceNotFoundError, DeviceOpenError
from ..logging_utils import get_logger
from .descriptors import DeviceId, lookup
from .transport import HidTransport, Transport, _import_hid

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
        hid = _import_hid()
    except DeviceOpenError:  # pragma: no cover - environment dependent
        log.warning("hidapi not available; cannot enumerate HID devices.")
        return []
    return list(hid.enumerate())


def _first_usage_page(data: bytes) -> int | None:
    """Return the first Usage Page value declared in a HID report descriptor."""
    i, n = 0, len(data)
    while i < n:
        prefix = data[i]
        if prefix == 0xFE:  # long item: [0xFE, size, tag, data...]
            size = data[i + 1] if i + 1 < n else 0
            i += 3 + size
            continue
        size = prefix & 0x03
        size = 4 if size == 3 else size
        # Usage Page is a Global item (type 0b01) with tag 0b0000 => prefix 0x04|size.
        if (prefix & 0xFC) == 0x04:
            return int.from_bytes(data[i + 1 : i + 1 + size], "little") if size else 0
        i += 1 + size
    return None


def _enrich_from_sysfs(
    path: bytes, product: str, manufacturer: str, usage_page: int
) -> tuple[str, str, int]:
    """Fill in product/manufacturer/usage_page from sysfs on Linux.

    On Linux the kernel may bind this keyboard to the ``apple`` driver, and
    ``hidapi`` then reports an empty product string and ``usage_page = 0``. The
    real values are still in sysfs; the hidapi path (e.g. ``3-4.4:1.0``) maps
    directly to ``/sys/bus/usb/devices/<path>``. This never raises.
    """
    if not sys.platform.startswith("linux"):
        return product, manufacturer, usage_page
    try:
        p = path.decode() if isinstance(path, bytes) else str(path)
    except Exception:
        return product, manufacturer, usage_page
    if ":" not in p:
        return product, manufacturer, usage_page

    base = Path("/sys/bus/usb/devices")
    iface_dir = base / p
    dev_dir = base / p.split(":", 1)[0]

    def _read(fp: Path) -> str:
        try:
            return fp.read_text().strip()
        except OSError:
            return ""

    if not product:
        product = _read(dev_dir / "product")
    if not manufacturer:
        manufacturer = _read(dev_dir / "manufacturer")
    if not usage_page:
        try:
            for rd in iface_dir.glob("*/report_descriptor"):
                up = _first_usage_page(rd.read_bytes())
                if up:
                    usage_page = up
                    break
        except OSError:
            pass
    return product, manufacturer, usage_page


def _to_discovered(entry: dict) -> DiscoveredDevice:
    vid = int(entry.get("vendor_id", 0))
    pid = int(entry.get("product_id", 0))
    path = entry.get("path", b"")
    product = str(entry.get("product_string") or "")
    manufacturer = str(entry.get("manufacturer_string") or "")
    usage_page = int(entry.get("usage_page", 0))

    # hidapi on Linux (apple driver) often leaves these blank/zero; recover them.
    if not product or not usage_page:
        product, manufacturer, usage_page = _enrich_from_sysfs(
            path, product, manufacturer, usage_page
        )

    return DiscoveredDevice(
        path=path,
        vendor_id=vid,
        product_id=pid,
        usage_page=usage_page,
        usage=int(entry.get("usage", 0)),
        interface_number=int(entry.get("interface_number", -1)),
        manufacturer=manufacturer,
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
