"""Logging configuration for NFV-MANO components."""

from __future__ import annotations

import logging

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging(component: str, level: int | str = logging.INFO) -> logging.Logger:
    """Configure and return a logger for a component.

    A single handler is attached to the component logger to avoid duplicated
    log lines when several components run in the same process (for example in
    tests).
    """
    logger = logging.getLogger(component)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, _DEFAULT_DATEFMT))
        logger.addHandler(handler)

    return logger
