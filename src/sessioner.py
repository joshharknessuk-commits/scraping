"""Session helpers for HTTP and Playwright interop."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests

from . import config


def make_session() -> requests.Session:
    """Create a configured ``requests`` session."""

    session = requests.Session()
    session.headers.update(config.HEADERS)
    return session


def load_playwright_cookies_into_session(session: requests.Session, cookies_path: str) -> None:
    """Load cookies exported from Playwright into a ``requests`` session."""

    path = Path(cookies_path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    cookies: Iterable[dict] = data
    for cookie in cookies:
        if "name" not in cookie or "value" not in cookie:
            continue
        cookie_args = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", "southwark.metastreet.co.uk"),
            "path": cookie.get("path", "/"),
        }
        if "expires" in cookie and cookie["expires"]:
            cookie_args["expires"] = int(cookie["expires"])
        session.cookies.set(**cookie_args)


def warmup(session: requests.Session) -> None:
    """Hit the search page to seed cookies and session state."""

    url = f"{config.BASE_URL}{config.SEARCH_PATH}"
    session.get(url, timeout=config.TIMEOUT)


__all__ = ["make_session", "load_playwright_cookies_into_session", "warmup"]
