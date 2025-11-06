"""Lambeth specific configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from common.config import BaseSettings, SnapshotMode

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "lambeth_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data" / "lambeth"

BASE_URL = "https://hmolicensing.lambeth.gov.uk/public-register"
COUNCIL_NAME = "Lambeth"
RESULT_CONTAINER_SELECTOR = "#main-content"
RESULT_LINK_PATTERN = re.compile(r"\b[A-Z]{3,5}-\d+\b", re.IGNORECASE)
DATASET_BASENAME = "lambeth_licences"


@dataclass(slots=True)
class Settings(BaseSettings):
    output_root: Path = field(default_factory=lambda: DEFAULT_OUTPUT_ROOT)
    snapshot_mode: SnapshotMode = SnapshotMode.NONE
