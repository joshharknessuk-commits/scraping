"""Lambeth scraper entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from common.models import LicenceRecord, ResultRow
from common.scraper import BasePostcodeScraper, FetchOutcome

from .config import COUNCIL_NAME, Settings, SOUP_PARSER
from .fetcher import fetch_record as fetch_pages
from .parser import (
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
)
from .search import search_postcode


class LambethScraper(BasePostcodeScraper):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings: Settings = settings or Settings()
        super().__init__(COUNCIL_NAME, self.settings)

    def search_postcode(
        self,
        env,
        postcode: str,
        save_html,
    ) -> List[ResultRow]:
        return search_postcode(env, postcode, self.settings, save_html)

    def fetch_record(
        self,
        env,
        row: ResultRow,
        postcode: str,
        detail_path: Path,
        additional_path: Path,
    ) -> FetchOutcome:
        return fetch_pages(
            env,
            row.reference,
            row.detail_url,
            postcode,
            self.settings,
            detail_path,
            additional_path,
        )

    def parse_record(
        self,
        row: ResultRow,
        outcome: FetchOutcome,
        postcode: str,
    ) -> LicenceRecord:
        detail_soup = BeautifulSoup(outcome.detail_html or "", SOUP_PARSER)
        additional_soup = BeautifulSoup(outcome.additional_html, SOUP_PARSER) if outcome.additional_html else None

        address = extract_address(detail_soup) or row.address
        licence_expiry = extract_expiry(detail_soup)
        licence_type = extract_licence_type(detail_soup) or extract_licence_type(row.summary_text)
        occupancy = extract_occupancy(additional_soup)

        return LicenceRecord(
            council=COUNCIL_NAME,
            reference=row.reference,
            address=address,
            occupancy=occupancy,
            licence_expiry=licence_expiry,
            licence_type=licence_type,
            detail_url=row.detail_url,
        )

    def detect_access_denied(self, detail_html: str, row: ResultRow) -> bool:
        content = (detail_html or "").lower()
        if "access denied" in content:
            return True
        if "support links" in content:
            return True
        if row.address and "support links" in row.address.lower():
            return True
        return False

    def build_metadata(
        self,
        record: LicenceRecord,
        row: ResultRow,
        outcome: FetchOutcome,
        detail_path: Path,
        additional_path: Path,
        postcode: str,
    ) -> dict:
        metadata = super().build_metadata(record, row, outcome, detail_path, additional_path, postcode)
        metadata.update(
            licence_type=record.licence_type,
            licence_expiry=record.licence_expiry,
            occupancy=record.occupancy,
        )
        return metadata


def run(postcodes: Optional[Iterable[str]] = None, settings: Optional[Settings] = None) -> List[LicenceRecord]:
    resolved_settings = settings or Settings()
    if postcodes is None:
        postcodes = _load_postcodes(resolved_settings.postcodes_path)
    scraper = LambethScraper(resolved_settings)
    return scraper.run(postcodes)


def _load_postcodes(path: Path) -> List[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
