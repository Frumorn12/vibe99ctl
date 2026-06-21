"""Exception hierarchy for vibe99ctl.

Keeping a single, well-defined hierarchy lets the CLI translate failures into
clean, user-facing messages (and proper exit codes) instead of leaking raw
tracebacks from the HID layer or Pillow.
"""

from __future__ import annotations


class Vibe99Error(Exception):
    """Base class for every error raised by this package."""


class DeviceNotFoundError(Vibe99Error):
    """No matching Vibe99 (or compatible) device was found on the system."""


class DeviceOpenError(Vibe99Error):
    """A device matched but could not be opened (permissions, busy, etc.)."""


class TransportError(Vibe99Error):
    """A low-level read/write to the device failed."""


class ProtocolError(Vibe99Error):
    """The device returned data we could not parse, or a command is malformed."""


class UnsupportedFeatureError(Vibe99Error):
    """A requested feature is not (yet) supported by the device or by this tool."""


class MediaError(Vibe99Error):
    """An image/animation/video could not be loaded or converted."""


class ValidationError(Vibe99Error):
    """User-supplied input failed validation before any device I/O happened."""
