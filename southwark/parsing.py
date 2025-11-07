"""HTML parsing helpers for the Southwark scraper."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Pattern, Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse as parse_date

from .models import ResultRow

SOUP_PARSER = "lxml"
LICENCE_TYPES = {
    "Additional licence": re.compile(r"additional\s+licen", re.IGNORECASE),
    "Selective licence": re.compile(r"selective\s+licen", re.IGNORECASE),
    "Mandatory licence": re.compile(r"mandatory\s+licen", re.IGNORECASE),
}
ADDRESS_SELECTORS: Iterable[str] = (
    "#main-content h1",
    "[data-testid='licence-address']",
    "article h1",
    "article h2",
    "main h1",
    "main h2",
    "h1",
    "h2",
)


def _normalise_date(text: str | None) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        parsed = parse_date(cleaned, dayfirst=True, fuzzy=True)
    except (ParserError, ValueError):
        return cleaned
    return parsed.date().isoformat()


def _extract_reference(text: str, pattern: Pattern[str]) -> Optional[str]:
    match = pattern.search(text)
    if match:
        return match.group().upper()
    return None


def _select_preferred_address(candidates: Sequence[str]) -> Optional[str]:
    if not candidates:
        return None
    postcode_pattern = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b", re.IGNORECASE)
    for candidate in candidates:
        if candidate.startswith("http"):
            continue
        if postcode_pattern.search(candidate):
            return candidate
    for candidate in candidates:
        if not candidate.startswith("http"):
            return candidate
    return candidates[0]


def parse_search_results(html: str, base_url: str, pattern: Pattern[str]) -> list[ResultRow]:
    soup = BeautifulSoup(html, SOUP_PARSER)
    rows: list[ResultRow] = []
    for heading in soup.select("h2"):
        anchor = heading.find("a", href=True)
        if not anchor:
            continue
        detail_href = anchor["href"]
        text = anchor.get_text(" ", strip=True)
        reference = _extract_reference(detail_href, pattern) or _extract_reference(text, pattern)
        if not reference:
            continue
        address = text or None
        paragraph = heading.find_next_sibling("p")
        summary_text = paragraph.get_text(" ", strip=True) if paragraph else ""
        detail_url = urljoin(base_url, detail_href)
        rows.append(
            ResultRow(
                reference=reference,
                address=address,
                detail_url=detail_url,
                summary_text=summary_text,
            )
        )
    return rows


def _extract_value_by_label(soup: BeautifulSoup, label_pattern: str) -> Optional[str]:
    regex = re.compile(label_pattern, re.IGNORECASE)
    for label in soup.select("dt"):
        label_text = label.get_text(" ", strip=True)
        if regex.search(label_text):
            dd = label.find_next_sibling("dd")
            if dd:
                text = dd.get_text(" ", strip=True)
                if text:
                    return text
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        header_text = cells[0].get_text(" ", strip=True)
        if regex.search(header_text):
            for cell in cells[1:]:
                text = cell.get_text(" ", strip=True)
                if text:
                    return text
    for string_node in soup.find_all(string=regex):
        parent = string_node.parent
        if not parent:
            continue
        sibling = parent.find_next_sibling()
        if sibling:
            text = sibling.get_text(" ", strip=True)
            if text:
                return text
        tokens = list(parent.stripped_strings)
        for index, token in enumerate(tokens):
            if regex.search(token) and index + 1 < len(tokens):
                return tokens[index + 1]
    return None


def extract_address(detail_soup: BeautifulSoup, row_hint: str | None = None) -> Optional[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for selector in ADDRESS_SELECTORS:
        for node in detail_soup.select(selector):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            if "landlord licence public register" in lowered:
                continue
            if "access denied" in lowered:
                continue
            if "support links" in lowered:
                continue
            seen.add(lowered)
            candidates.append(text)
    if row_hint:
        candidates.append(row_hint)
    return _select_preferred_address(candidates)


def extract_expiry(detail_soup: BeautifulSoup) -> Optional[str]:
    value = _extract_value_by_label(
        detail_soup,
        r"(licen[cs]e\s+expiry|licen[cs]e\s+end\s+date|end\s+date)",
    )
    return _normalise_date(value)


def extract_licence_type(source: BeautifulSoup | str | None) -> Optional[str]:
    if source is None:
        return None
    values = source.stripped_strings if isinstance(source, BeautifulSoup) else [source]
    for value in values:
        for label, pattern in LICENCE_TYPES.items():
            if pattern.search(value):
                return label
    return None


def find_additional_info_url(detail_soup: BeautifulSoup, detail_url: str) -> Optional[str]:
    anchor = detail_soup.select_one("a[href*='licence-application-additional-info']")
    if anchor and anchor.has_attr("href"):
        href = anchor["href"]
        return urljoin(detail_url, href)
    base_url = detail_url.split("?", 1)[0].rstrip("/")
    if base_url:
        return f"{base_url}/licence-application-additional-info"
    return None


def extract_occupancy(additional_soup: Optional[BeautifulSoup]) -> Optional[int]:
    if additional_soup is None:
        return None
    value = _extract_value_by_label(
        additional_soup,
        r"maximum\s+permitted\s+occupants|max\s+occupants|permitted\s+occupants",
    )
    if not value:
        return None
    digits = re.search(r"\d+", value.replace(",", ""))
    if digits:
        try:
            return int(digits.group())
        except ValueError:
            return None
    return None
