"""Entry point for scraping the Southwark register."""

from __future__ import annotations

from typing import Iterable, List

from common.config import ScraperSettings
from common.models import LicenceRecord
from common.runner import ScraperHooks, run_scraper

from .config import COUNCIL, Settings
from .parser import (
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
    find_additional_info_url,
    parse_search_results,
)


def run(postcodes: Iterable[str], settings: ScraperSettings | None = None) -> List[LicenceRecord]:
    """Scrape the register for the supplied postcodes."""

    resolved_settings = settings or Settings()
    if resolved_settings.council != COUNCIL:
        raise ValueError("Southwark runner received settings for a different council")

    hooks = ScraperHooks(
        parse_search_results=parse_search_results,
        find_additional_info_url=find_additional_info_url,
        extract_address=extract_address,
        extract_expiry=extract_expiry,
        extract_licence_type=extract_licence_type,
        extract_occupancy=extract_occupancy,
    )

    return run_scraper(postcodes, resolved_settings, hooks)


if __name__ == "__main__":  # pragma: no cover
    from .cli import main

    main()
