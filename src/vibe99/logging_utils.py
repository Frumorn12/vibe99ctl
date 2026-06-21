"""Centralised logging configuration.

We use the stdlib :mod:`logging` so libraries can hook in, but render through
Rich for readable, colourised console output. The CLI calls :func:`configure`
once at startup based on ``-v/--verbose`` flags.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

LOGGER_NAME = "vibe99"

# A single shared console so stdout/stderr formatting stays consistent and is
# easy to capture in tests.
console = Console(stderr=True)


def configure(verbosity: int = 0) -> logging.Logger:
    """Configure the package logger.

    :param verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG.
    :returns: the configured package logger.
    """
    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)

    handler = RichHandler(
        console=console,
        show_time=False,
        show_path=verbosity >= 2,
        rich_tracebacks=True,
        markup=True,
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the package namespace."""
    if name is None:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
