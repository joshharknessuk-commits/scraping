"""Fetch Lambeth detail and additional HTML."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from common.browser import BrowserEnv
from common.config import SnapshotMode
from common.scraper import FetchOutcome
from common.storage import load_cached_html

from .config import Settings, SOUP_PARSER
from .parser import find_additional_info_url


def fetch_record(
    env: BrowserEnv,
    reference: str,
    detail_url: str,
    _postcode: str,
    settings: Settings,
    detail_path: Path,
    additional_path: Path,
) -> FetchOutcome:
    if settings.dry_run:
        return _load_fixture(reference, settings)

    detail_html: Optional[str] = None
    additional_html: Optional[str] = None
    detail_from_cache = False
    additional_from_cache = False

    if (
        settings.snapshot_mode == SnapshotMode.ALL
        and not settings.force_refresh
        and detail_path.exists()
    ):
        detail_html = load_cached_html(detail_path)
        detail_from_cache = detail_html is not None

    if detail_html is None:
        detail_html = _fetch_html(env, detail_url, settings, label=f"detail-{reference}", optional=False)

    if not detail_html:
        return FetchOutcome(None, None, None)

    detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
    additional_url = find_additional_info_url(detail_soup, detail_url)

    if additional_url:
        if (
            settings.snapshot_mode == SnapshotMode.ALL
            and not settings.force_refresh
            and additional_path.exists()
        ):
            additional_html = load_cached_html(additional_path)
            additional_from_cache = additional_html is not None

        if additional_html is None:
            additional_html = _fetch_html(
                env,
                additional_url,
                settings,
                label=f"additional-{reference}",
                optional=True,
            )

    return FetchOutcome(
        detail_html=detail_html,
        additional_html=additional_html,
        additional_url=additional_url,
        detail_from_cache=detail_from_cache,
        additional_from_cache=additional_from_cache,
    )


def _fetch_html(
    env: BrowserEnv,
    url: str,
    settings: Settings,
    *,
    label: str,
    optional: bool,
) -> Optional[str]:
    def _attempt() -> str:
        with env.page() as page:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            env.wait_for_idle(page)
            return page.content()

    try:
        return env.with_retries(_attempt, label=label)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        env.logger.warning("Timeout fetching %s (%s): %s", label, url, exc)
        if optional:
            return None
        raise


def _load_fixture(reference: str, settings: Settings) -> FetchOutcome:
    detail_fixture = settings.fixtures_dir / "detail" / f"{reference}.html"
    additional_fixture = settings.fixtures_dir / "additional" / f"{reference}.html"

    detail_html = detail_fixture.read_text(encoding="utf-8")
    additional_html = None
    additional_url = None

    if additional_fixture.exists():
        additional_html = additional_fixture.read_text(encoding="utf-8")
        additional_url = "fixture://additional"

    return FetchOutcome(
        detail_html=detail_html,
        additional_html=additional_html,
        additional_url=additional_url,
        detail_from_cache=False,
        additional_from_cache=False,
    )
