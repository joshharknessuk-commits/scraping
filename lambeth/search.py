"""Search workflow for the Lambeth register."""

from __future__ import annotations

import logging
from typing import Callable, List, Set

from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from common.browser import BrowserEnv
from common.models import ResultRow

from .config import BASE_URL, RESULT_CONTAINER_SELECTOR, Settings
from .parser import parse_search_results

SaveHtmlCallback = Callable[[str, int, str], None]


def search_postcode(
    env: BrowserEnv,
    postcode: str,
    settings: Settings,
    save_html: SaveHtmlCallback,
) -> List[ResultRow]:
    if settings.dry_run:
        return _load_fixture_results(postcode, settings, save_html, env.logger)

    with env.page() as page:
        env.logger.info("Searching postcode %s", postcode)

        def _attempt_load() -> None:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            env.wait_for_idle(page)

        env.with_retries(_attempt_load, label=f"load-base:{postcode}")
        env.throttle()

        try:
            input_locator = page.locator("input[name='search[query]']")
            input_locator.wait_for(state="visible", timeout=settings.timeout_ms)
            input_locator.fill(postcode)
        except PlaywrightTimeoutError as exc:
            env.logger.warning("Timeout locating search input for %s", postcode)
            raise exc

        env.throttle()

        try:
            button_locator = page.locator("form[name='search'] button[type='submit']")
            button_locator.wait_for(state="visible", timeout=settings.timeout_ms)
            button_locator.click()
        except PlaywrightTimeoutError as exc:
            env.logger.warning("Timeout locating search button for %s", postcode)
            raise exc

        seen_urls: Set[str] = set()
        page_index = 0
        results: List[ResultRow] = []

        while True:
            current_url = page.url
            if current_url in seen_urls:
                env.logger.warning("Detected repeated page (%s) for %s; stopping pagination", current_url, postcode)
                break
            seen_urls.add(current_url)

            page_index += 1

            if not _wait_for_results(env, page, postcode, settings):
                break

            html = page.inner_html(RESULT_CONTAINER_SELECTOR)
            save_html(postcode, page_index, html)
            page_rows = parse_search_results(html)
            results.extend(page_rows)
            env.logger.info(
                "Postcode %s page %s produced %s rows (total=%s)",
                postcode,
                page_index,
                len(page_rows),
                len(results),
            )

            if settings.max_pagination_pages and page_index >= settings.max_pagination_pages:
                env.logger.info(
                    "Reached pagination limit (%s pages) for postcode %s",
                    settings.max_pagination_pages,
                    postcode,
                )
                break

            if not _go_to_next_page(env, page, settings):
                break
            env.throttle()

        env.logger.info("Finished postcode %s with %s total rows", postcode, len(results))
        return results


def _wait_for_results(env: BrowserEnv, page, postcode: str, settings: Settings) -> bool:
    try:
        page.wait_for_function(
            """
            selector => {
                const container = document.querySelector(selector);
                if (container && container.querySelector("h2 a")) {
                    return true;
                }
                const body = document.body;
                const text = body && typeof body.innerText === 'string' ? body.innerText : '';
                return text.includes('No results found');
            }
            """,
            arg=RESULT_CONTAINER_SELECTOR,
            timeout=settings.timeout_ms,
        )
    except PlaywrightTimeoutError:
        env.logger.warning("Timed out waiting for results for %s", postcode)
        return False

    has_rows = page.locator(f"{RESULT_CONTAINER_SELECTOR} h2 a").count() > 0
    if not has_rows:
        if page.locator("text='No results found'").count() > 0:
            env.logger.info("No results for %s", postcode)
            return False
        env.logger.warning("No recognised results markers for %s", postcode)
        return False
    return True


def _go_to_next_page(env: BrowserEnv, page, settings: Settings) -> bool:
    next_button = page.locator("a.button", has_text="Next")
    if not next_button.count():
        env.logger.debug("Pagination next button absent; stopping")
        return False

    if next_button.get_attribute("aria-disabled") == "true":
        env.logger.debug("Pagination next button disabled; stopping")
        return False

    def _attempt() -> None:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=settings.timeout_ms):
            next_button.click()
        env.wait_for_idle(page)

    try:
        env.with_retries(_attempt, label="pagination-next")
    except (PlaywrightTimeoutError, PlaywrightError):
        env.logger.warning("Timed out navigating to next page")
        return False
    return True


def _load_fixture_results(
    postcode: str, settings: Settings, save_html: SaveHtmlCallback, logger: logging.Logger
) -> List[ResultRow]:
    fixture_name = postcode.replace(" ", "_").upper() + ".html"
    path = settings.fixtures_dir / "search" / fixture_name
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Dry-run fixture missing for %s (%s)", postcode, path)
        return []
    save_html(postcode, 1, html)
    return parse_search_results(html)
