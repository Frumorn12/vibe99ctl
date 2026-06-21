"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from PIL import Image

from vibe99.device.transport import DryRunTransport


@pytest.fixture
def dry_transport() -> DryRunTransport:
    return DryRunTransport()


@pytest.fixture
def solid_image() -> Image.Image:
    """A 240x240 solid red image."""
    return Image.new("RGB", (240, 240), (255, 0, 0))


@pytest.fixture
def fake_hid_enumeration(monkeypatch):
    """Patch discovery enumeration with a controllable device list."""
    from vibe99.device import discovery

    entries: list[dict] = []

    def _set(new_entries: list[dict]) -> None:
        entries.clear()
        entries.extend(new_entries)

    monkeypatch.setattr(discovery, "_enumerate_raw", lambda: list(entries))
    return _set
