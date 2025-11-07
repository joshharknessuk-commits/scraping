"""Playwright helpers for manual CAPTCHA completion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from playwright.sync_api import sync_playwright

from . import config


def capture_and_save_cookies(cookies_path: str) -> None:
    """Open Chromium so a human can solve the CAPTCHA and persist cookies.

    This function intentionally keeps the human in the loop: it launches a headed
    Chromium instance, navigates to the public register search page, and asks the
    user to solve any CAPTCHA prompts manually. Once satisfied, press Enter in the
    terminal and the captured cookies will be written to ``cookies_path`` for
    later reuse with ``requests``.
    """

    path = Path(cookies_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{config.BASE_URL}{config.SEARCH_PATH}", wait_until="networkidle")
        input("Solve any CAPTCHA in the browser, then press Enter here to continue...")
        cookies: List[dict[str, Any]] = context.cookies()
        with path.open("w", encoding="utf-8") as fh:
            json.dump(cookies, fh, indent=2)
        context.close()
        browser.close()


__all__ = ["capture_and_save_cookies"]
