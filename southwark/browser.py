"""Simple Patchright browser helpers for the Southwark scraper."""

from __future__ import annotations

import random
import time
from contextlib import AbstractContextManager

from patchright.sync_api import Browser, Error, Playwright, TimeoutError, sync_playwright


class BrowserSession(AbstractContextManager[Browser]):
    """Context manager that launches a single Chromium browser instance."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> Browser:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        return self._browser

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()


def fetch_with_retries(
    browser: Browser,
    url: str,
    *,
    timeout_ms: int,
    retries: int,
    backoff: float,
    delay_range: tuple[float, float],
) -> str:
    """Fetch ``url`` returning the final HTML, applying simple retry logic."""

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms // 2)
            except TimeoutError:
                pass
            content = page.content()
            return content
        except (TimeoutError, Error) as exc:
            last_error = exc
            if attempt == retries:
                break
            sleep_seconds = backoff * attempt
            time.sleep(sleep_seconds)
        finally:
            try:
                page.close()
            except Exception:
                pass
            time.sleep(random.uniform(*delay_range))
    assert last_error is not None
    raise last_error
