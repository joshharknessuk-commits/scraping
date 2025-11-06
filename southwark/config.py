"""Southwark scraper configuration and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from common.config import ScraperSettings

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "southwark_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data"
DEFAULT_FIXTURES_DIR = PACKAGE_ROOT / "fixtures"

BASE_URL = "https://southwark.metastreet.co.uk/public-register"
COUNCIL_NAME = "Southwark"
REFERENCE_PATTERN = r"\bSWK-\d+\b"
SOUP_PARSER = "lxml"
RESULT_CONTAINER_SELECTOR = "#main-content"


@dataclass(slots=True)
class Settings(ScraperSettings):
    council_slug: str = "southwark"
    base_output_name: str = "southwark_licences"
    base_url: str = BASE_URL
    postcode_pattern: str = REFERENCE_PATTERN
    soup_parser: str = SOUP_PARSER
    postcodes_path: Path = field(default_factory=lambda: DEFAULT_POSTCODES_PATH)
    fixtures_dir: Path = field(default_factory=lambda: DEFAULT_FIXTURES_DIR)

    def __post_init__(self) -> None:
        if self.output_root == Path("data"):
            self.output_root = DEFAULT_OUTPUT_ROOT
        ScraperSettings.__post_init__(self)
        self.fixtures_dir = self.fixtures_dir.resolve()
        self.postcodes_path = self.postcodes_path.resolve()
