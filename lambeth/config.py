"""Lambeth scraper configuration and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from common.config import ScraperSettings

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTCODES_PATH = PACKAGE_ROOT.parent / "lambeth_postcodes.txt"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT.parent / "data"
DEFAULT_FIXTURES_DIR = PACKAGE_ROOT / "fixtures"

BASE_URL = "https://hmolicensing.lambeth.gov.uk/public-register"
COUNCIL_NAME = "Lambeth"
REFERENCE_PATTERN = r"\b[A-Z]{3,5}-\d+\b"
SOUP_PARSER = "lxml"
RESULT_CONTAINER_SELECTOR = "#main-content"


@dataclass(slots=True)
class Settings(ScraperSettings):
    council_slug: str = "lambeth"
    base_output_name: str = "lambeth_licences"
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
