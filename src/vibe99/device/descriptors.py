"""Known/likely USB identities for the Mechlands Vibe99 and siblings.

None of these IDs are officially published by Mechlands. They are seeded from
devices in the same OEM family (the keyboards driven by the ``controlhub.top`` /
``qmk.top`` WebHID drivers, e.g. the AttackShark K86), which is the most likely
silicon/firmware lineage for the Vibe99.

Every entry carries an explicit ``confidence`` level so the CLI can tell the user
"this is a guess" instead of pretending certainty. Run ``vibe99 list-devices --all``
on your own keyboard and please open an issue with the real VID/PID so we can
promote an entry to ``confirmed``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Confidence = Literal["confirmed", "probable", "guess"]


@dataclass(frozen=True)
class DeviceId:
    """A USB identity plus metadata about how sure we are."""

    vendor_id: int
    product_id: int
    name: str
    confidence: Confidence = "guess"
    # Optional hints to disambiguate the control interface among several HID
    # interfaces. ``None`` means "don't filter on this".
    usage_page: int | None = None
    usage: int | None = None
    interface_number: int | None = None
    # Substring required in the USB product string for this entry to match.
    # CRUCIAL for the Vibe99: it shares VID:PID 05ac:024f with real Apple
    # keyboards, so we must also check the product string ("Mechlands Vibe99")
    # to avoid ever talking to an actual Apple keyboard.
    product_match: str | None = None
    notes: str = ""

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    def matches(self, vendor_id: int, product_id: int, product: str = "") -> bool:
        if self.vendor_id != vendor_id or self.product_id != product_id:
            return False
        if self.product_match is not None:
            return self.product_match.lower() in (product or "").lower()
        return True


# --------------------------------------------------------------------------- #
# The table. CONFIRMED on real hardware (report descriptors read from sysfs).
#
# The Vibe99 is a SONiX-based keyboard that reuses Apple's VID:PID 05ac:024f.
# We therefore REQUIRE the product string "Vibe99" so we never match a genuine
# Apple keyboard sharing that ID. The wired keyboard reports product
# "SONiX Mechlands Vibe99"; the 2.4G dongle reports "2.4G Wireless Receiver".
# --------------------------------------------------------------------------- #
KNOWN_DEVICES: list[DeviceId] = [
    DeviceId(
        vendor_id=0x05AC,
        product_id=0x024F,
        name="Mechlands Vibe99 (wired, SONiX)",
        confidence="confirmed",
        usage_page=0xFF13,  # control interface; screen is on 0xFF68
        usage=0x01,
        product_match="vibe99",
        notes="Confirmed via report descriptor: control=0xFF13, screen=0xFF68.",
    ),
    DeviceId(
        vendor_id=0x05AC,
        product_id=0x024F,
        name="Mechlands Vibe99 (2.4G receiver, SONiX)",
        confidence="confirmed",
        usage_page=0xFF60,
        usage=0x61,
        product_match="2.4g wireless receiver",
        notes="Wireless dongle; vendor reports are smaller. Prefer WIRED for config.",
    ),
]


# Convenience views used by discovery.
KNOWN_VID_PID: set[tuple[int, int]] = {(d.vendor_id, d.product_id) for d in KNOWN_DEVICES}


def lookup(vendor_id: int, product_id: int, product: str = "") -> DeviceId | None:
    """Return the catalog entry for a device, if known.

    ``product`` is the USB product string; it is required to disambiguate the
    Apple VID:PID collision (see :class:`DeviceId.product_match`).
    """
    for dev in KNOWN_DEVICES:
        if dev.matches(vendor_id, product_id, product):
            return dev
    return None


@dataclass
class CatalogStats:
    confirmed: int = 0
    probable: int = 0
    guess: int = 0
    entries: list[DeviceId] = field(default_factory=list)


def catalog_stats() -> CatalogStats:
    stats = CatalogStats(entries=list(KNOWN_DEVICES))
    for dev in KNOWN_DEVICES:
        setattr(stats, dev.confidence, getattr(stats, dev.confidence) + 1)
    return stats
