"""Patchright browser utilities with resilience helpers."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import Counter
from contextlib import contextmanager
from typing import Callable, Optional, TypeVar

from patchright.sync_api import (
    Browser as PlaywrightBrowser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    sync_playwright,
)

from .config import ScraperSettings

T = TypeVar("T")


class BrowserEnv:
    """Context manager that owns a Patchright browser instance."""

    def __init__(self, settings: ScraperSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = threading.RLock()
        self._rng = random.Random()
        if settings.seed is not None:
            self._rng.seed(settings.seed + int(time.time() * 1000) + threading.get_ident())
        self.retry_summary: Counter[str] = Counter()

    def __enter__(self) -> "BrowserEnv":
        self._playwright = sync_playwright().start()
        launch_kwargs = {"headless": self.settings.headless}
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context()
        self._configure_context(self._context)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:  # noqa: ANN001
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._context is not None:
                try:
                    self._context.close()
                except PlaywrightError as exc:  # pragma: no cover - defensive logging
                    self.logger.debug("Context close failed: %s", exc)
                self._context = None
            if self._browser is not None:
                try:
                    self._browser.close()
                except PlaywrightError as exc:  # pragma: no cover - defensive logging
                    self.logger.debug("Browser close failed: %s", exc)
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None

    def new_page(self) -> Page:
        with self._lock:
            if self._context is None:
                raise RuntimeError("Browser context not initialised")
            page = self._context.new_page()
        page.set_default_timeout(self.settings.timeout_ms)
        page.set_default_navigation_timeout(self.settings.timeout_ms)
        return page

    def restart_context(self) -> None:
        with self._lock:
            if self._browser is None:
                raise RuntimeError("Browser not initialised")
            if self._context is not None:
                try:
                    self._context.close()
                except PlaywrightError as exc:
                    self.logger.debug("Context close during restart failed: %s", exc)
            self._context = self._browser.new_context()
            self._configure_context(self._context)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def throttle(self) -> None:
        delay = self._rng.uniform(*self.settings.delay_range)
        time.sleep(delay)

    def with_retries(
        self,
        fn: Callable[[], T],
        label: str,
        *,
        attempts: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> T:
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
                self.logger.warning("%s attempt %s/%s failed: %s", label, attempt, max_attempts, exc)
                self.retry_summary["retries"] += 1
                self.retry_summary[f"{label}-retries"] += 1
                time.sleep(delay)
                delay *= 2
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{label} failed without executing function")

    @contextmanager
    def page(self) -> Page:
        page = self.new_page()
        try:
            yield page
        finally:
            try:
                page.close()
            except PlaywrightError as exc:  # pragma: no cover - defensive logging
                self.logger.debug("Page close failed: %s", exc)

    def _block_heavy_resources(self, route, request) -> None:  # noqa: ANN001
        try:
            if request.resource_type in {"image", "media", "font"}:
                route.abort()
            else:
                route.continue_()
        except PlaywrightError as exc:  # pragma: no cover - defensive logging
            self.logger.debug("Route handling failed: %s", exc)

    def _configure_context(self, context: BrowserContext) -> None:
        context.set_default_timeout(self.settings.timeout_ms)
        context.set_default_navigation_timeout(self.settings.timeout_ms)
        context.route("**/*", self._block_heavy_resources)
