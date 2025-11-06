"""Southwark specific configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from common.config import BaseSettings, SnapshotMode

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "southwark_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data" / "southwark"

BASE_URL = "https://southwark.metastreet.co.uk/public-register"
COUNCIL_NAME = "Southwark"
RESULT_CONTAINER_SELECTOR = "#main-content"
RESULT_LINK_PATTERN = re.compile(r"\bSWK-\d+\b", re.IGNORECASE)
DATASET_BASENAME = "southwark_licences"


@dataclass(slots=True)
class Settings(BaseSettings):
    output_root: Path = field(default_factory=lambda: DEFAULT_OUTPUT_ROOT)
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
