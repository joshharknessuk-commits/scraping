"""Utility helpers for the Southwark landlord licence scraper."""
from __future__ import annotations

import functools
import time
from datetime import datetime, timezone
from typing import Any, Callable, Tuple, Type, TypeVar
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from . import config

T = TypeVar("T")


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.now(timezone.utc).isoformat()


def normalize_detail_url(url: str) -> str:
    """Normalise a licence detail URL to an absolute form without transient params."""

    absolute = urljoin(config.BASE_URL, url)
    parsed = urlsplit(absolute)
    query_items = [item for item in parse_qsl(parsed.query, keep_blank_values=True) if item[0] != "_t"]
    query = urlencode(query_items)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def retry(
    *,
    max_attempts: int = 3,
    backoff_factor: float = 1.5,
    exceptions: Tuple[Type[BaseException], ...] = (requests.RequestException,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff for network-bound operations."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 1
            delay = 1.0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= max_attempts:
                        raise
                    time.sleep(delay)
                    delay *= backoff_factor
                    attempt += 1

        return wrapper

    return decorator


__all__ = ["now_iso", "normalize_detail_url", "retry"]
