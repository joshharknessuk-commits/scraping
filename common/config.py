"""Shared configuration objects used across council scrapers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Tuple

DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_DELAY_RANGE = (0.75, 1.5)
DEFAULT_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_REFRESH_INTERVAL = 250
DEFAULT_ACCESS_DENIED_RETRIES = 3
DEFAULT_ACCESS_DENIED_BACKOFF = 10.0


class SnapshotMode(str, Enum):
    """Control how aggressively HTML snapshots are persisted."""

    NONE = "none"
    ALL = "all"

    def __str__(self) -> str:  # pragma: no cover - display helper
        return self.value


@dataclass(slots=True)
class ScraperSettings:
    """Base configuration shared by every council scraper."""

    council_slug: str
    base_output_name: str = "licences"
    output_root: Path = field(default_factory=lambda: Path("data"))
    headless: bool = True
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    min_delay: float = DEFAULT_DELAY_RANGE[0]
    max_delay: float = DEFAULT_DELAY_RANGE[1]
    max_pagination_pages: int | None = None
    force_refresh: bool = False
    log_level: int = logging.INFO
    retries: int = DEFAULT_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
    seed: int | None = None
    concurrency: int = 1
    jsonl_output: bool = False
    json_array_output: bool = True
    refresh_interval: int | None = DEFAULT_REFRESH_INTERVAL
    access_denied_retries: int = DEFAULT_ACCESS_DENIED_RETRIES
    access_denied_backoff: float = DEFAULT_ACCESS_DENIED_BACKOFF
    dry_run: bool = False

    def __post_init__(self) -> None:
        if not self.council_slug:
            raise ValueError("council_slug must be provided")
        if self.min_delay < 0 or self.max_delay < 0:
            raise ValueError("Delay bounds must be non-negative")
        if self.min_delay > self.max_delay:
            raise ValueError("min_delay cannot exceed max_delay")
        if self.timeout_ms < 1_000:
            raise ValueError("timeout_ms must be at least 1000 ms")
        if self.retries < 1:
            raise ValueError("retries must be >= 1")
        if self.retry_base_delay <= 0:
            raise ValueError("retry_base_delay must be positive")
        if self.retry_backoff_factor < 1:
            raise ValueError("retry_backoff_factor must be >= 1")
        if self.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if self.refresh_interval is not None and self.refresh_interval < 0:
            raise ValueError("refresh_interval must be non-negative")
        if self.access_denied_retries < 1:
            raise ValueError("access_denied_retries must be >= 1")
        if self.access_denied_backoff < 0:
            raise ValueError("access_denied_backoff must be >= 0")
        self.output_root = self.output_root.resolve()

    @property
    def delay_range(self) -> Tuple[float, float]:
        """Return the throttling delay range."""

        return (self.min_delay, self.max_delay)

    def council_output_root(self) -> Path:
        """Path where council-specific artefacts should be written."""

        return self.output_root / self.council_slug

    def dataset_filename(self) -> str:
        """Canonical JSON dataset filename."""

        return f"{self.base_output_name}.json"

    def jsonl_filename(self) -> str:
        """Canonical JSONL dataset filename."""

        return f"{self.base_output_name}.jsonl"
