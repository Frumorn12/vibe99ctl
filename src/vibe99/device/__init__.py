"""Device layer: identity table, discovery, and HID transport."""

from __future__ import annotations

from .descriptors import KNOWN_DEVICES, DeviceId
from .discovery import DiscoveredDevice, find_devices, open_device
from .transport import DryRunTransport, HidTransport, Transport

__all__ = [
    "KNOWN_DEVICES",
    "DeviceId",
    "DiscoveredDevice",
    "DryRunTransport",
    "HidTransport",
    "Transport",
    "find_devices",
    "open_device",
]
