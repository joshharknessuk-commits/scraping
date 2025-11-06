"""Shared postcode search flow built on Patchright."""

from __future__ import annotations

from typing import Callable, List, Set

from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from .browser import BrowserEnv
from .config import ScraperSettings
from .models import ResultRow

SaveHtmlCallback = Callable[[str, int, str], None]
ParseResults = Callable[[str], List[ResultRow]]


def search_postcode(
    env: BrowserEnv,
    postcode: str,
    settings: ScraperSettings,
    save_html: SaveHtmlCallback,
    parse_results: ParseResults,
) -> List[ResultRow]:
    page = env.new_page()
    env.logger.info("Searching postcode %s", postcode)

    try:
        _load_search_page(env, page, postcode, settings)
        env.throttle()
        _fill_search_form(env, page, postcode, settings)

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

            html = page.inner_html(settings.council.result_container_selector)
            save_html(postcode, page_index, html)

            rows = parse_results(html)
            results.extend(rows)
            env.logger.info(
                "Postcode %s page %s produced %s rows (total=%s)",
                postcode,
                page_index,
                len(rows),
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

        return results
    finally:
        page.close()
        env.logger.info("Finished postcode %s with %s total rows", postcode, len(results))


def _load_search_page(env: BrowserEnv, page, postcode: str, settings: ScraperSettings) -> None:
    def _attempt() -> None:
        page.goto(settings.council.base_url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=settings.timeout_ms // 2)
        except PlaywrightTimeoutError:
            pass

    env.with_retries(_attempt, label=f"load-base:{postcode}")


def _fill_search_form(env: BrowserEnv, page, postcode: str, settings: ScraperSettings) -> None:
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


def _wait_for_results(env: BrowserEnv, page, postcode: str, settings: ScraperSettings) -> bool:
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
            arg=settings.council.result_container_selector,
            timeout=settings.timeout_ms,
        )
    except PlaywrightTimeoutError:
        env.logger.warning("Timed out waiting for results for %s", postcode)
        return False

    has_rows = page.locator(f"{settings.council.result_container_selector} h2 a").count() > 0
    if not has_rows:
        if page.locator("text='No results found'").count() > 0:
            env.logger.info("No results for %s", postcode)
            return False
        env.logger.warning("No recognised results markers for %s", postcode)
        return False
    return True


def _go_to_next_page(env: BrowserEnv, page, settings: ScraperSettings) -> bool:
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
        try:
            page.wait_for_load_state("networkidle", timeout=settings.timeout_ms // 2)
        except PlaywrightTimeoutError:
            pass

    try:
        env.with_retries(_attempt, label="pagination-next")
    except (PlaywrightTimeoutError, PlaywrightError):
        env.logger.warning("Timed out navigating to next page")
        return False
    return True
