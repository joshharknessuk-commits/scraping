"""Southwark-specific configuration helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common.config import CouncilConfig, ScraperSettings, SnapshotMode

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "southwark_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data" / "southwark"

COUNCIL = CouncilConfig(
    name="Southwark",
    slug="southwark",
    base_url="https://southwark.metastreet.co.uk/public-register",
    result_container_selector="#main-content",
    reference_pattern=re.compile(r"\bSWK-\d+\b", re.IGNORECASE),
)


def Settings(**kwargs: Any) -> ScraperSettings:
    """Return a configured :class:`ScraperSettings` for Southwark."""

    output_root = kwargs.pop("output_root", None) or DEFAULT_OUTPUT_ROOT
    return ScraperSettings(council=COUNCIL, output_root=output_root, **kwargs)


__all__ = [
    "COUNCIL",
    "DEFAULT_POSTCODES_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "Settings",
    "SnapshotMode",
]
