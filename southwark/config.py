"""Configuration objects for the Southwark scraper."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_BASE_URL = "https://southwark.metastreet.co.uk/public-register"
DEFAULT_RESULT_CONTAINER = "#main-content"
DEFAULT_OUTPUT_ROOT = Path("data") / "southwark"
DEFAULT_FIXTURES_DIR = Path("tests/fixtures/southwark")
DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_DELAY_RANGE: Tuple[float, float] = (0.75, 1.5)
DEFAULT_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 1.5


class SnapshotMode(str, Enum):
    """Controls whether HTML snapshots are written to disk."""

    NONE = "none"
    ALL = "all"

    def __str__(self) -> str:  # pragma: no cover - used by CLI help
        return self.value


@dataclass(slots=True)
class SouthwarkSettings:
    """Runtime configuration for the Southwark scraper."""

    output_dir: Path = DEFAULT_OUTPUT_ROOT
    base_url: str = DEFAULT_BASE_URL
    result_container_selector: str = DEFAULT_RESULT_CONTAINER
    headless: bool = True
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    delay_range: Tuple[float, float] = DEFAULT_DELAY_RANGE
    max_pages_per_postcode: Optional[int] = None
    retries: int = DEFAULT_RETRIES
    retry_backoff: float = DEFAULT_RETRY_BACKOFF
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
    jsonl_output: bool = True
    json_output: bool = True
    force_refresh: bool = False
    dry_run: bool = False
    fixtures_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.dry_run and self.fixtures_dir is None:
            self.fixtures_dir = DEFAULT_FIXTURES_DIR.resolve()
        if self.fixtures_dir is not None:
            self.fixtures_dir = Path(self.fixtures_dir).resolve()

        min_delay, max_delay = self.delay_range
        if min_delay < 0 or max_delay < 0:
            raise ValueError("Delay bounds must be non-negative")
        if min_delay > max_delay:
            raise ValueError("min_delay cannot exceed max_delay")
        if self.timeout_ms < 1_000:
            raise ValueError("timeout_ms must be >= 1000")
        if self.retries < 1:
            raise ValueError("retries must be >= 1")


def load_postcodes(path: Path) -> list[str]:
    """Return a list of postcodes from a newline-delimited text file."""

    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


__all__ = [
    "SouthwarkSettings",
    "SnapshotMode",
    "load_postcodes",
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_BASE_URL",
    "DEFAULT_RESULT_CONTAINER",
    "DEFAULT_TIMEOUT_MS",
    "DEFAULT_DELAY_RANGE",
    "DEFAULT_RETRIES",
    "DEFAULT_RETRY_BACKOFF",
]
