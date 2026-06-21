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
    notes: str = ""

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    def matches(self, vendor_id: int, product_id: int) -> bool:
        return self.vendor_id == vendor_id and self.product_id == product_id


# --------------------------------------------------------------------------- #
# The table. Order matters only for display; matching is by (vid, pid).
# --------------------------------------------------------------------------- #
KNOWN_DEVICES: list[DeviceId] = [
    # Seeded from the AttackShark K86 reverse-engineering effort, which targets
    # the same OEM web driver the Vibe99 is believed to share.
    DeviceId(
        vendor_id=0x3151,
        product_id=0x4011,
        name="Mechlands Vibe99 (probable, shared OEM family)",
        confidence="probable",
        usage_page=0xFF00,
        notes="Same family as controlhub.top/qmk.top WebHID devices.",
    ),
    DeviceId(
        vendor_id=0x3151,
        product_id=0x4015,
        name="Mechlands Vibe99 / sibling (probable)",
        confidence="probable",
        usage_page=0xFF00,
        notes="Sibling PID observed on related screen keyboards.",
    ),
    # Placeholder for the wired-mode interface, which can enumerate under a
    # different PID than the 2.4G dongle. Fill in once measured.
    DeviceId(
        vendor_id=0x3151,
        product_id=0x4010,
        name="Mechlands Vibe99 wired (guess)",
        confidence="guess",
        usage_page=0xFF00,
        notes="Placeholder for the wired control interface; verify on hardware.",
    ),
]


# Convenience views used by discovery.
KNOWN_VID_PID: set[tuple[int, int]] = {(d.vendor_id, d.product_id) for d in KNOWN_DEVICES}


def lookup(vendor_id: int, product_id: int) -> DeviceId | None:
    """Return the catalog entry for a (vid, pid) pair, if known."""
    for dev in KNOWN_DEVICES:
        if dev.matches(vendor_id, product_id):
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
