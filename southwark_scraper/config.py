"""Configuration and default constants for the Southwark scraper."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Tuple

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "southwark_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data" / "southwark"

BASE_URL = "https://southwark.metastreet.co.uk/public-register"
COUNCIL_NAME = "Southwark"

RESULT_CONTAINER_SELECTOR = "#main-content"
RESULT_LINK_PATTERN = re.compile(r"\bSWK-\d+\b", re.IGNORECASE)

SOUP_PARSER = "lxml"

DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_DELAY_RANGE = (0.75, 1.5)
DEFAULT_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_REFRESH_INTERVAL = 250
DEFAULT_ACCESS_DENIED_RETRIES = 3
DEFAULT_ACCESS_DENIED_BACKOFF = 10.0


class SnapshotMode(str, Enum):
    """Control how the scraper persists HTML snapshots to disk."""

    NONE = "none"
    ALL = "all"

    def __str__(self) -> str:  # pragma: no cover - used implicitly by argparse help
        return self.value


@dataclass(slots=True)
class Settings:
    """Runtime settings for the Southwark scraper."""

    output_root: Path = field(default_factory=lambda: DEFAULT_OUTPUT_ROOT)
    headless: bool = True
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    min_delay: float = DEFAULT_DELAY_RANGE[0]
    max_delay: float = DEFAULT_DELAY_RANGE[1]
    max_pagination_pages: int | None = None
    force_refresh: bool = False
    log_level: int = logging.INFO
    retries: int = DEFAULT_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
    seed: int | None = None
    concurrency: int = 1
    jsonl_output: bool = False
    json_array_output: bool = True
    refresh_interval: int = DEFAULT_REFRESH_INTERVAL
    access_denied_retries: int = DEFAULT_ACCESS_DENIED_RETRIES
    access_denied_backoff: float = DEFAULT_ACCESS_DENIED_BACKOFF

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

    @property
    def delay_range(self) -> Tuple[float, float]:
        return (self.min_delay, self.max_delay)
