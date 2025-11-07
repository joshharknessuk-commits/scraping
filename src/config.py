"""Configuration constants for the Southwark landlord licence scraper."""
from __future__ import annotations

from typing import Dict

BASE_URL = "https://southwark.metastreet.co.uk"
SEARCH_PATH = "/public-register"
DETAIL_PREFIX = "/public-register/"
ADDITIONAL_SUFFIX = "/licence-application-additional-info"

HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}{SEARCH_PATH}",
}

RATE_LIMIT_SECONDS = 0.8
TIMEOUT = 30

OUTPUT_JSON = "out/licences.json"
OUTPUT_JSONL = "out/licences.jsonl"
LINKS_CSV = "out/licence_links.csv"
COOKIES_FILE = "out/cookies.json"

COUNCIL = "Southwark"
