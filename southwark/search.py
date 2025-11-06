"""Southwark postcode search flow wrapper."""

from __future__ import annotations

from common.search import search_postcode as _search_postcode

from .config import BASE_URL, RESULT_CONTAINER_SELECTOR, Settings
from .parse import parse_search_results


def search_postcode(env, postcode: str, settings: Settings, save_html):
    return _search_postcode(
        env,
        postcode,
        settings,
        save_html,
        base_url=BASE_URL,
        result_container_selector=RESULT_CONTAINER_SELECTOR,
        parse_search_results=parse_search_results,
    )
