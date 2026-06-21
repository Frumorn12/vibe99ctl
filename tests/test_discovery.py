from __future__ import annotations

from vibe99.device.descriptors import KNOWN_DEVICES
from vibe99.device.discovery import (
    enumerate_all,
    find_devices,
    select_control_interface,
)


def _entry(vid, pid, iface, usage_page, product="kbd"):
    return {
        "path": f"/dev/hidraw{iface}".encode(),
        "vendor_id": vid,
        "product_id": pid,
        "usage_page": usage_page,
        "usage": 0x01,
        "interface_number": iface,
        "manufacturer_string": "Mechlands",
        "product_string": product,
        "serial_number": "X",
    }


def test_find_devices_filters_to_catalog(fake_hid_enumeration):
    known = KNOWN_DEVICES[0]
    fake_hid_enumeration(
        [
            _entry(known.vendor_id, known.product_id, 0, 0x0001),  # keyboard iface
            _entry(known.vendor_id, known.product_id, 1, 0xFF00),  # vendor iface
            _entry(0x1234, 0x5678, 0, 0xFF00),  # unrelated device
        ]
    )

    matched = find_devices()
    assert len(matched) == 2
    assert all(d.catalog is not None for d in matched)

    all_devices = find_devices(include_unknown=True)
    assert len(all_devices) == 3


def test_select_prefers_vendor_interface(fake_hid_enumeration):
    known = KNOWN_DEVICES[0]
    fake_hid_enumeration(
        [
            _entry(known.vendor_id, known.product_id, 0, 0x0001),
            _entry(known.vendor_id, known.product_id, 1, 0xFF00),
        ]
    )
    chosen = select_control_interface(find_devices())
    assert chosen is not None
    assert chosen.usage_page == 0xFF00


def test_enumerate_all_handles_empty(fake_hid_enumeration):
    fake_hid_enumeration([])
    assert enumerate_all() == []
