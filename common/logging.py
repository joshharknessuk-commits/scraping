"""Logging helpers shared across scrapers."""

from __future__ import annotations

import logging
from pathlib import Path


def get_logger(name: str, log_dir: Path, level: int) -> logging.Logger:
    """Configure a logger that writes to both console and a rolling fetch.log."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    file_path = log_dir / "fetch.log"
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) != str(file_path):
            logger.removeHandler(handler)
            handler.close()

    if not any(
        isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == str(file_path)
        for handler in logger.handlers
    ):
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    if not any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger
