"""Lambeth postcode search flow built on shared helpers."""

from __future__ import annotations

from typing import List

from common.browser import BrowserEnv
from common.config import ScraperSettings
from common.models import ResultRow
from common.search import SaveHtmlCallback, search_postcode as shared_search_postcode

from .parser import parse_search_results


def search_postcode(
    env: BrowserEnv,
    postcode: str,
    settings: ScraperSettings,
    save_html: SaveHtmlCallback,
) -> List[ResultRow]:
    return shared_search_postcode(env, postcode, settings, save_html, parse_search_results)
