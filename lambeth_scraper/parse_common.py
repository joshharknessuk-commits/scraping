"""Shared parsing helpers."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence

from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse as parse_date


def normalise_date(text: str | None) -> Optional[str]:
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


def extract_value_by_label(soup: BeautifulSoup, label_pattern: str) -> Optional[str]:
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


def extract_reference(text: str, pattern: str = r"\bSWK-\d+\b") -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group().upper()
    return None


def select_preferred_address(candidates: Sequence[str]) -> Optional[str]:
    if not candidates:
        return None

    postcode_pattern = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b", re.IGNORECASE)
    for candidate in candidates:
        if postcode_pattern.search(candidate):
            return candidate

    return candidates[0] if candidates else None
