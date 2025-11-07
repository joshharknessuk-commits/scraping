"""HTML parsing and fetching for Southwark licence detail pages."""
from __future__ import annotations

import re
from typing import Dict, Optional, Union

import requests
from bs4 import BeautifulSoup

from . import config
from .ajaxcom import safe_response_to_html
from .utils import retry

LICENCE_PATTERN = re.compile(r"SWK-\d+")
OCCUPANCY_LABELS = [
    "occupancy",
    "maximum occupancy",
    "maximum number of occupants",
    "maximum permitted occupants",
    "max occupants",
    "number of occupants",
]


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def parse_detail_html(html: str) -> Dict[str, Optional[str]]:
    """Parse key fields from a licence detail page."""

    soup = BeautifulSoup(html, "html.parser")
    address = _clean_text(
        soup.find("h1", class_="heading-large").get_text(strip=True)
        if soup.find("h1", class_="heading-large")
        else None
    )

    licence_reference: Optional[str] = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "span", "strong", "b"]):
        text = tag.get_text(strip=True)
        match = LICENCE_PATTERN.search(text)
        if match:
            licence_reference = match.group(0)
            break

    def _find_field(label: str) -> Optional[str]:
        for paragraph in soup.find_all("p"):
            text = paragraph.get_text(" ", strip=True)
            if label in text.lower():
                bold = paragraph.find("span", class_="bold")
                if bold:
                    return _clean_text(bold.get_text(strip=True))
                strong = paragraph.find("strong")
                if strong:
                    return _clean_text(strong.get_text(strip=True))
                return _clean_text(paragraph.get_text(strip=True).split(":")[-1])
        return None

    licence_type = _find_field("licence type")
    end_date = _find_field("licence end date")

    return {
        "address": address,
        "licence_reference": licence_reference,
        "licence_type": licence_type,
        "end_date": end_date,
    }


def parse_additional_html_for_occupancy(html: str) -> Union[int, str, None]:
    """Extract occupancy information from the additional details page."""

    soup = BeautifulSoup(html, "html.parser")
    for label in OCCUPANCY_LABELS:
        pattern = re.compile(re.escape(label), re.IGNORECASE)
        for block in soup.find_all(["p", "li", "div", "span"]):
            text = block.get_text(" ", strip=True)
            if not text or not pattern.search(text):
                continue
            candidate = None
            bold = block.find("span", class_="bold") or block.find("strong") or block.find("b")
            if bold:
                candidate = bold.get_text(strip=True)
            if not candidate:
                candidate = text
            if candidate:
                numbers = re.findall(r"\d+", candidate)
                if numbers:
                    try:
                        return int(numbers[0])
                    except ValueError:
                        return candidate
                return candidate
    return None


@retry()
def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """Fetch a licence detail page and return the HTML body."""

    response = session.get(detail_url, timeout=config.TIMEOUT)
    response.raise_for_status()
    return safe_response_to_html(response)


@retry()
def fetch_additional(session: requests.Session, additional_url: str) -> str:
    """Fetch a licence additional information page and return the HTML body."""

    response = session.get(additional_url, timeout=config.TIMEOUT)
    response.raise_for_status()
    return safe_response_to_html(response)


__all__ = [
    "parse_detail_html",
    "parse_additional_html_for_occupancy",
    "fetch_detail",
    "fetch_additional",
]
