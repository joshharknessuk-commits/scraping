"""Compatibility wrapper for programmatic entry points."""

from __future__ import annotations

from typing import Iterable, List

from .config import SouthwarkSettings
from .models import LicenceRecord
from .scraper import run as scrape


def run(postcodes: Iterable[str], settings: SouthwarkSettings | None = None) -> List[LicenceRecord]:
    """Scrape the Southwark register for ``postcodes``."""

    return scrape(postcodes, settings)


def main() -> None:  # pragma: no cover
    from .cli import main as cli_main

    cli_main()


if __name__ == "__main__":  # pragma: no cover
    main()
