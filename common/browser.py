"""Helpers for working with Patchright's synchronous Playwright API."""

from __future__ import annotations

import logging
import random
import threading
import time
from contextlib import contextmanager
from typing import Callable, Generator, Optional, TypeVar

from patchright.sync_api import (
    Browser as PlaywrightBrowser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .config import ScraperSettings

T = TypeVar("T")

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}


class BrowserEnv:
    """Context manager that owns a Playwright browser session."""

    def __init__(self, settings: ScraperSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None
        self._context_lock = threading.RLock()

    def __enter__(self) -> "BrowserEnv":
        self._playwright = sync_playwright().start()
        browser_args = {"headless": self.settings.headless}
        self._browser = self._playwright.chromium.launch(**browser_args)
        self._context = self._browser.new_context()
        self._configure_context(self._context)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        with self._context_lock:
            if self._context is not None:
                try:
                    self._context.close()
                except PlaywrightError as exc:  # pragma: no cover - defensive cleanup
                    self.logger.debug("Error closing context: %s", exc)
                self._context = None
            if self._browser is not None:
                try:
                    self._browser.close()
                except PlaywrightError as exc:  # pragma: no cover - defensive cleanup
                    self.logger.debug("Error closing browser: %s", exc)
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None

    def new_page(self) -> Page:
        """Create a new page from the active browser context."""

        with self._context_lock:
            context = self._ensure_context()
            return context.new_page()

    @contextmanager
    def page(self) -> Generator[Page, None, None]:
        """Yield a page and ensure it is closed afterwards."""

        page = self.new_page()
        try:
            yield page
        finally:
            try:
                page.close()
            except PlaywrightError as exc:  # pragma: no cover - defensive cleanup
                self.logger.debug("Error closing page: %s", exc)

    def restart_context(self) -> None:
        """Dispose of the current context and create a new one."""

        with self._context_lock:
            if self._browser is None:
                raise RuntimeError("Browser not initialised")
            if self._context is not None:
                try:
                    self._context.close()
                except PlaywrightError as exc:
                    self.logger.debug("Error closing context during restart: %s", exc)
            self._context = self._browser.new_context()
            self._configure_context(self._context)

    def throttle(self) -> None:
        """Sleep for a random amount of time within the configured bounds."""

        delay = random.uniform(*self.settings.delay_range)
        if delay > 0:
            time.sleep(delay)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def with_retries(
        self,
        fn: Callable[[], T],
        *,
        label: str,
        attempts: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> T:
        """Execute ``fn`` with exponential backoff retries."""

        max_attempts = attempts or self.settings.retries
        delay = base_delay or self.settings.retry_base_delay
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= max_attempts:
                    self.logger.error("%s failed after %s attempts: %s", label, attempt, exc)
                    raise
                self.logger.warning(
                    "%s attempt %s/%s failed: %s", label, attempt, max_attempts, exc
                )
                time.sleep(delay)
                delay *= self.settings.retry_backoff_factor
        if last_exc is not None:  # pragma: no cover - defensive fallback
            raise last_exc
        raise RuntimeError(f"{label} failed without executing function")

    def wait_for_idle(self, page: Page) -> None:
        """Wait for the network to settle on the supplied page."""

        try:
            page.wait_for_load_state("networkidle", timeout=self.settings.timeout_ms // 2)
        except PlaywrightTimeoutError:
            self.logger.debug("Network idle wait timed out; continuing")

    def _ensure_context(self) -> BrowserContext:
        if self._browser is None:
            raise RuntimeError("Browser not initialised")
        if self._context is None:
            self._context = self._browser.new_context()
            self._configure_context(self._context)
        return self._context

    def _configure_context(self, context: BrowserContext) -> None:
        try:
            context.route("**/*", self._block_heavy_resources)
        except PlaywrightError as exc:  # pragma: no cover - defensive logging
            self.logger.debug("Failed to register route handler: %s", exc)

    def _block_heavy_resources(self, route, request) -> None:
        """Abort large resource types to keep things lean."""

        try:
            if request.resource_type in _BLOCKED_RESOURCE_TYPES:
                route.abort()
            else:
                route.continue_()
        except PlaywrightError as exc:  # pragma: no cover - diagnostics only
            self.logger.debug("Route handling error: %s", exc)
