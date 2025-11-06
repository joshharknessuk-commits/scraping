"""Dataclasses shared between council scrapers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ResultRow:
    """Representation of a single row returned from a postcode search."""

    reference: str
    detail_url: str
    summary_text: str | None = None
    address: str | None = None


@dataclass(slots=True)
class LicenceRecord:
    """Structured representation of a scraped licence."""

    council: str
    reference: str
    detail_url: str
    address: Optional[str] = None
    licence_type: Optional[str] = None
    licence_expiry: Optional[str] = None
    occupancy: Optional[int] = None


@dataclass(slots=True)
class ScrapePaths:
    """Locations on disk where scraper artefacts are stored."""

    root: Path
    search_dir: Path
    licence_dir: Path
    additional_dir: Path
    json_path: Path
    jsonl_path: Path
    metadata_path: Path
    log_dir: Path
