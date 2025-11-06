"""Shared infrastructure for council scrapers."""

from .config import CouncilConfig, ScraperSettings, SnapshotMode
from .models import LicenceRecord, ResultRow

__all__ = [
    "CouncilConfig",
    "ScraperSettings",
    "SnapshotMode",
    "LicenceRecord",
    "ResultRow",
]
