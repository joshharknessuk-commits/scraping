"""Logging helpers for the Southwark scraper."""

from __future__ import annotations

import logging
from pathlib import Path


def get_logger(name: str, log_dir: Path, level: int) -> logging.Logger:
    """Configure a logger that writes to both console and fetch.log."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    file_path = log_dir / "fetch.log"
    existing_file_handlers = [
        handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)
    ]
    for handler in existing_file_handlers:
        # Recreate the handler if the log file changed (e.g. different output root).
        if getattr(handler, "baseFilename", None) != str(file_path):
            logger.removeHandler(handler)
            handler.close()

    has_target_file_handler = any(
        getattr(handler, "baseFilename", None) == str(file_path)
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    )
    if not has_target_file_handler:
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    has_console_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    )
    if not has_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger
