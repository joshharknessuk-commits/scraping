"""Southwark parsing utilities built on shared helpers."""

from __future__ import annotations

from bs4 import BeautifulSoup

from common.parsing import (
    extract_address as shared_extract_address,
    extract_expiry as shared_extract_expiry,
    extract_licence_type as shared_extract_licence_type,
    extract_occupancy as shared_extract_occupancy,
    find_additional_info_url as shared_find_additional_info_url,
    parse_search_results as shared_parse_search_results,
)
from common.models import ResultRow

from .config import COUNCIL


def parse_search_results(html: str) -> list[ResultRow]:
    return shared_parse_search_results(html, COUNCIL.base_url, COUNCIL.reference_pattern)


def extract_address(detail_soup: BeautifulSoup, row_hint: str | None = None) -> str | None:
    return shared_extract_address(detail_soup, row_hint)


def extract_expiry(detail_soup: BeautifulSoup) -> str | None:
    return shared_extract_expiry(detail_soup)


def extract_licence_type(source: BeautifulSoup | str | None) -> str | None:
    return shared_extract_licence_type(source)


def find_additional_info_url(detail_soup: BeautifulSoup, detail_url: str) -> str | None:
    return shared_find_additional_info_url(detail_soup, detail_url)


def extract_occupancy(additional_soup: BeautifulSoup | None) -> int | None:
    return shared_extract_occupancy(additional_soup)
