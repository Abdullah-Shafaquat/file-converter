"""Structured logging setup."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.addHandler(handler)

    # Uvicorn installs its own handlers; keep ours as the single sink.
    logging.getLogger("uvicorn.access").handlers = [handler]

    _CONFIGURED = True
