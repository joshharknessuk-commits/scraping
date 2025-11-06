"""Fetch helpers shared by council scrapers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping, Optional, Tuple

from bs4 import BeautifulSoup
from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from .browser import BrowserEnv
from .config import ScraperSettings, SnapshotMode, SOUP_PARSER
from .storage import load_cached_html


def fetch_pages(
    env: BrowserEnv,
    reference: str,
    detail_url: str,
    settings: ScraperSettings,
    cache_paths: Mapping[str, Path],
    force: bool,
    find_additional_info_url: Callable[[BeautifulSoup, str], Optional[str]],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    detail_path = cache_paths.get("detail")
    additional_path = cache_paths.get("additional")

    detail_html: Optional[str] = None
    additional_html: Optional[str] = None
    additional_url: Optional[str] = None

    if not force and detail_path is not None and settings.snapshot_mode == SnapshotMode.ALL:
        detail_html = load_cached_html(detail_path)
        if detail_html:
            env.logger.info("Loaded cached detail HTML for %s", reference)

    if detail_html is None:
        detail_html = _fetch_html(env, detail_url, settings, label=f"detail-{reference}", optional=False)
        if detail_html is None:
            env.logger.warning("Failed to fetch detail page for %s", reference)
            return None, None, None
        env.logger.info("Fetched detail HTML for %s", reference)

    detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
    additional_url = find_additional_info_url(detail_soup, detail_url)

    if additional_url:
        if not force and additional_path is not None and settings.snapshot_mode == SnapshotMode.ALL:
            additional_html = load_cached_html(additional_path)
            if additional_html:
                env.logger.info("Loaded cached additional HTML for %s", reference)

        if additional_html is None:
            additional_html = _fetch_html(
                env,
                additional_url,
                settings,
                label=f"additional-{reference}",
                optional=True,
            )
            if additional_html:
                env.logger.info("Fetched additional HTML for %s", reference)
            else:
                env.logger.info("No additional HTML retrieved for %s", reference)
    else:
        env.logger.info("No additional info link for %s", reference)
    return detail_html, additional_html, additional_url


def _fetch_html(
    env: BrowserEnv,
    url: str,
    settings: ScraperSettings,
    *,
    label: str,
    optional: bool,
) -> Optional[str]:
    def _attempt() -> str:
        page = env.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=settings.timeout_ms // 2)
            except PlaywrightTimeoutError:
                pass
            return page.content()
        finally:
            env.throttle()
            page.close()

    try:
        return env.with_retries(_attempt, label=label)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        env.logger.warning("Timeout fetching %s (%s): %s", label, url, exc)
        if optional:
            return None
        raise
