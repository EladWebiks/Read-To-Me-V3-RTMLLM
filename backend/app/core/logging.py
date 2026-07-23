"""Structured logging bootstrap."""

from __future__ import annotations

import logging
import sys


def configure_logging(*, debug: bool = False) -> None:
    """Configure root logging for the API process."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
