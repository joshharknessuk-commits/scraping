"""Patchright browser management helpers."""

from __future__ import annotations

import logging
import random
import threading
import time
from contextlib import suppress
from typing import Callable, Optional, TypeVar

from patchright.sync_api import (
    Browser as PlaywrightBrowser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .config import BaseSettings

T = TypeVar("T")


class BrowserEnv:
    """Context manager that owns the Patchright browser and context."""

    def __init__(self, settings: BaseSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = threading.RLock()

    def __enter__(self) -> "BrowserEnv":
        with self._lock:
            if self._playwright is not None:
                return self
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.settings.headless)
            self._context = self._browser.new_context()
            self._configure_context(self._context)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:  # noqa: D401 - context manager API
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._context is not None:
                with suppress(PlaywrightError):
                    self._context.close()
                self._context = None
            if self._browser is not None:
                with suppress(PlaywrightError):
                    self._browser.close()
                self._browser = None
            if self._playwright is not None:
                with suppress(Exception):  # Patchright stop may raise plain Exception
                    self._playwright.stop()
                self._playwright = None

    def new_page(self) -> Page:
        with self._lock:
            if self._context is None:
                raise RuntimeError("Browser context not initialised")
            return self._context.new_page()

    def restart_context(self) -> None:
        with self._lock:
            if self._browser is None:
                raise RuntimeError("Browser not initialised")
            if self._context is not None:
                with suppress(PlaywrightError):
                    self._context.close()
            self._context = self._browser.new_context()
            self._configure_context(self._context)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def throttle(self) -> None:
        lower, upper = self.settings.delay_range
        if upper <= 0:
            return
        delay = random.uniform(lower, upper)
        time.sleep(delay)

    def with_retries(
        self,
        fn: Callable[[], T],
        *,
        label: str,
        attempts: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> T:
        max_attempts = attempts or self.settings.retries
        delay = base_delay or self.settings.retry_base_delay
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - propagate after retries
                last_exc = exc
                if attempt >= max_attempts:
                    self.logger.error("%s failed after %s attempts: %s", label, attempt, exc)
                    raise
                self.logger.warning("%s attempt %s/%s failed: %s", label, attempt, max_attempts, exc)
                time.sleep(delay)
                delay *= 2
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{label} failed without executing function")

    def _configure_context(self, context: BrowserContext) -> None:
        def _block_heavy(route, request) -> None:
            try:
                if request.resource_type in {"image", "media", "font"}:
                    route.abort()
                else:
                    route.continue_()
            except PlaywrightError as exc:  # pragma: no cover - defensive logging
                self.logger.debug("Route handling failed: %s", exc)

        context.set_default_navigation_timeout(self.settings.timeout_ms)
        context.set_default_timeout(self.settings.timeout_ms)
        context.route("**/*", _block_heavy)
