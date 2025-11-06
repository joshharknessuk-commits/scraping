"""Shared configuration objects and enums for the scrapers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Tuple

SOUP_PARSER = "lxml"


class SnapshotMode(str, Enum):
    """Control how aggressively HTML snapshots are persisted to disk."""

    NONE = "none"
    ALL = "all"

    def __str__(self) -> str:  # pragma: no cover - for argparse friendliness
        return self.value


@dataclass(slots=True)
class BaseSettings:
    """Runtime options that apply to any council scraper."""

    output_root: Path
    headless: bool = True
    timeout_ms: int = 30_000
    min_delay: float = 0.75
    max_delay: float = 1.5
    max_pagination_pages: int | None = None
    force_refresh: bool = False
    log_level: int = logging.INFO
    retries: int = 3
    retry_base_delay: float = 1.0
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
    seed: int | None = None
    concurrency: int = 1
    jsonl_output: bool = False
    json_array_output: bool = True
    refresh_interval: int | None = 250
    access_denied_retries: int = 3
    access_denied_backoff: float = 10.0
    dry_run: bool = False
    fixture_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.min_delay < 0 or self.max_delay < 0:
            raise ValueError("Delay bounds must be non-negative")
        if self.min_delay > self.max_delay:
            raise ValueError("min_delay cannot exceed max_delay")
        if self.timeout_ms < 1_000:
            raise ValueError("timeout_ms must be at least 1000")
        if self.retries < 1:
            raise ValueError("retries must be at least 1")
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.refresh_interval is not None and self.refresh_interval < 0:
            raise ValueError("refresh_interval must be non-negative")
        if self.access_denied_retries < 1:
            raise ValueError("access_denied_retries must be at least 1")
        if self.access_denied_backoff < 0:
            raise ValueError("access_denied_backoff must be non-negative")

        self.output_root = self.output_root.resolve()
        if self.fixture_dir is not None:
            self.fixture_dir = self.fixture_dir.resolve()

    @property
    def delay_range(self) -> Tuple[float, float]:
        return (self.min_delay, self.max_delay)
