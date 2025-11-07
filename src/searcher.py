"""Search page navigation helpers."""
from __future__ import annotations

import re
import time
from typing import Iterator, List, Optional, Set

import requests
from bs4 import BeautifulSoup

from . import config
from .ajaxcom import safe_response_to_html
from .utils import normalize_detail_url, retry

DETAIL_LINK_RE = re.compile(r"/public-register/SWK-\d+")


@retry()
def get_results_page(session: requests.Session, query: str, page: int) -> str:
    """Fetch and return the search results HTML for the given query/page."""

    params = {"search[query]": query, "page": page}
    url = f"{config.BASE_URL}{config.SEARCH_PATH}"
    response = session.get(url, params=params, timeout=config.TIMEOUT)
    response.raise_for_status()
    return safe_response_to_html(response)


def extract_detail_links_from_results_html(html: str) -> List[str]:
    """Extract and normalise detail links from a results page."""

    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for anchor in soup.find_all("a", href=DETAIL_LINK_RE):
        href = anchor.get("href")
        if not href:
            continue
        links.append(normalize_detail_url(href))
    return links


def iterate_all_detail_links(
    session: requests.Session,
    query: str,
    start_page: int = 1,
    max_pages: Optional[int] = None,
) -> Iterator[str]:
    """Iterate through paginated search results yielding unique detail URLs."""

    seen: Set[str] = set()
    page = start_page
    while True:
        if max_pages is not None and page > max_pages:
            break
        html = get_results_page(session, query, page)
        urls = extract_detail_links_from_results_html(html)
        if not urls:
            break
        new_urls = [url for url in urls if url not in seen]
        if not new_urls and max_pages is None:
            break
        for url in new_urls:
            seen.add(url)
            yield url
        page += 1
        time.sleep(config.RATE_LIMIT_SECONDS)


__all__ = [
    "get_results_page",
    "extract_detail_links_from_results_html",
    "iterate_all_detail_links",
]
