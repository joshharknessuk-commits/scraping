"""Southwark-specific parsing utilities."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import BASE_URL, SOUP_PARSER
from .models import ResultRow
from .parse_common import extract_reference, extract_value_by_label, normalise_date, select_preferred_address

LICENCE_TYPES = {
    "additional": "Additional licence",
    "selective": "Selective licence",
    "mandatory": "Mandatory licence",
}

LICENCE_TYPE_PATTERNS = {
    label: re.compile(rf"\b{key}\b.*licen", re.IGNORECASE)
    for key, label in LICENCE_TYPES.items()
}

ADDRESS_SELECTORS: Iterable[str] = (
    "#main-content h1.heading-large",
    "[data-testid='licence-address']",
    ".licence-address",
    "article h1",
    "article h2",
    "main h1",
    "main h2",
    "h1",
    "h2",
)


def parse_search_results(html: str) -> List[ResultRow]:
    soup = BeautifulSoup(html, SOUP_PARSER)
    rows: List[ResultRow] = []

    for heading in soup.select("h2"):
        anchor = heading.find("a", href=True)
        if not anchor:
            continue

        detail_href = anchor["href"]
        reference = extract_reference(detail_href) or extract_reference(anchor.get_text(" ", strip=True))
        if not reference:
            continue

        address = anchor.get_text(" ", strip=True) or None
        info = heading.find_next_sibling("p")
        summary_text = info.get_text(" ", strip=True) if info else ""
        detail_url = urljoin(BASE_URL, detail_href)

        rows.append(
            ResultRow(
                reference=reference,
                address=address,
                detail_url=detail_url,
                summary_text=summary_text,
            ),
        )
    return rows


def extract_address(detail_soup: BeautifulSoup) -> Optional[str]:
    candidates: List[str] = []
    for selector in ADDRESS_SELECTORS:
        for node in detail_soup.select(selector):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if "landlord licence public register" in lowered:
                continue
            if "access denied" in lowered:
                continue
            if "support links" in lowered:
                continue
            candidates.append(text)
    return select_preferred_address(candidates)


def extract_expiry(detail_soup: BeautifulSoup) -> Optional[str]:
    value = extract_value_by_label(
        detail_soup,
        r"(licence\s+end\s+date|licen[cs]e\s+expiry|end\s+date)",
    )
    return normalise_date(value)


def extract_licence_type(source: BeautifulSoup | str | None) -> Optional[str]:
    if source is None:
        return None
    strings = source.stripped_strings if isinstance(source, BeautifulSoup) else (source.strip(),)
    for item in strings:
        for label, pattern in LICENCE_TYPE_PATTERNS.items():
            if pattern.search(item):
                return label
    return None


def find_additional_info_url(detail_soup: BeautifulSoup, detail_url: str) -> Optional[str]:
    anchor = detail_soup.select_one("a[href*='licence-application-additional-info']")
    if anchor and anchor.has_attr("href"):
        href = anchor["href"]
        resolved = urljoin(detail_url, href)
        if resolved:
            return resolved

    base_url = detail_url.split("?", 1)[0].rstrip("/")
    if base_url:
        return f"{base_url}/licence-application-additional-info"
    return None


def extract_occupancy(additional_soup: Optional[BeautifulSoup]) -> Optional[int]:
    if additional_soup is None:
        return None
    value = extract_value_by_label(
        additional_soup,
        r"maximum\s+permitted\s+occupants|max\s+occupants|permitted\s+occupants",
    )
    if not value:
        return None
    match = re.search(r"\d+", value.replace(",", ""))
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None
