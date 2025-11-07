"""Helpers for parsing AjaxCom style responses."""
from __future__ import annotations

import json
from typing import Iterable, List

import requests


def extract_main_html(ops_json: Iterable[dict]) -> str:
    """Extract HTML payload targeting the main content container from AjaxCom ops."""

    html_parts: List[str] = []
    for op in ops_json:
        operation = op.get("operation")
        options = op.get("options", {})
        if operation != "container":
            continue
        if options.get("method") != "html":
            continue
        target = options.get("target", "")
        if "#main-content" not in str(target):
            continue
        value = options.get("value")
        if isinstance(value, str):
            html_parts.append(value)
    return "".join(html_parts)


def safe_response_to_html(response: requests.Response) -> str:
    """Return HTML from a response, unpacking AjaxCom JSON documents when required."""

    content_type = response.headers.get("Content-Type", "")
    text = response.text
    if "application/json" in content_type.lower():
        try:
            payload = response.json()
        except ValueError:
            return text
        html = extract_main_html(payload if isinstance(payload, list) else payload.get("ops", []))
        return html or text
    try:
        payload = json.loads(text)
    except ValueError:
        return text
    html = extract_main_html(payload if isinstance(payload, list) else payload.get("ops", []))
    return html or text


__all__ = ["extract_main_html", "safe_response_to_html"]
