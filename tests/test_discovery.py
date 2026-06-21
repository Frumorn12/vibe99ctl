from __future__ import annotations

from vibe99.config import CONTROL_USAGE_PAGE, SCREEN_USAGE_PAGE
from vibe99.device.descriptors import lookup
from vibe99.device.discovery import (
    _first_usage_page,
    enumerate_all,
    find_devices,
    find_screen_interface,
    select_control_interface,
)


def test_first_usage_page_parses_real_descriptors():
    # Real bytes captured from a connected Vibe99 (docs/protocol.md Appendix A).
    screen = bytes.fromhex("0668ff0961a101096215")  # 06 68 ff -> page 0xFF68
    control = bytes.fromhex("0613ff0901a10115")  # 06 13 ff -> page 0xFF13
    keyboard = bytes.fromhex("05010906a101")  # 05 01    -> page 0x0001
    assert _first_usage_page(screen) == 0xFF68
    assert _first_usage_page(control) == 0xFF13
    assert _first_usage_page(keyboard) == 0x0001
    assert _first_usage_page(b"") is None

VIBE_VID = 0x05AC
VIBE_PID = 0x024F


def _entry(iface, usage_page, product="SONiX Mechlands Vibe99"):
    return {
        "path": f"/dev/hidraw{iface}".encode(),
        "vendor_id": VIBE_VID,
        "product_id": VIBE_PID,
        "usage_page": usage_page,
        "usage": 0x01,
        "interface_number": iface,
        "manufacturer_string": "SONiX",
        "product_string": product,
        "serial_number": "X",
    }


def test_catalog_requires_product_string():
    # Same VID:PID as a real Apple keyboard, but the Apple product string must
    # NOT be identified as a Vibe99.
    assert lookup(VIBE_VID, VIBE_PID, "Aluminium Keyboard") is None
    match = lookup(VIBE_VID, VIBE_PID, "SONiX Mechlands Vibe99")
    assert match is not None
    assert match.confidence == "confirmed"


def test_find_devices_filters_to_catalog(fake_hid_enumeration):
    fake_hid_enumeration(
        [
            _entry(0, 0x0001),  # keyboard interface (Vibe99)
            _entry(3, CONTROL_USAGE_PAGE),  # vendor control interface
            # A genuine Apple keyboard sharing the VID:PID must be ignored.
            _entry(0, 0x0001, product="Aluminium Keyboard"),
            {  # unrelated device
                "path": b"/dev/hidrawX",
                "vendor_id": 0x1234,
                "product_id": 0x5678,
                "usage_page": 0xFF00,
                "usage": 1,
                "interface_number": 0,
                "manufacturer_string": "Acme",
                "product_string": "Thing",
                "serial_number": "Y",
            },
        ]
    )

    matched = find_devices()
    assert len(matched) == 2
    assert all(d.catalog is not None for d in matched)
    assert all("vibe99" in d.product.lower() for d in matched)

    assert len(find_devices(include_unknown=True)) == 4


def test_select_prefers_control_interface(fake_hid_enumeration):
    fake_hid_enumeration(
        [
            _entry(0, 0x0001),
            _entry(2, SCREEN_USAGE_PAGE),
            _entry(3, CONTROL_USAGE_PAGE),
        ]
    )
    chosen = select_control_interface(find_devices())
    assert chosen is not None
    assert chosen.usage_page == CONTROL_USAGE_PAGE


def test_find_screen_interface(fake_hid_enumeration):
    fake_hid_enumeration([_entry(2, SCREEN_USAGE_PAGE), _entry(3, CONTROL_USAGE_PAGE)])
    screen = find_screen_interface(find_devices())
    assert screen is not None
    assert screen.usage_page == SCREEN_USAGE_PAGE


def test_enumerate_all_handles_empty(fake_hid_enumeration):
    fake_hid_enumeration([])
    assert enumerate_all() == []
