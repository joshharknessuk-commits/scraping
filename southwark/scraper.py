"""Southwark scraping orchestration."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from patchright.sync_api import TimeoutError

from .browser import BrowserSession, fetch_with_retries
from .config import SnapshotMode, SouthwarkSettings
from .models import LicenceRecord, ResultRow
from .parsing import (
    SOUP_PARSER,
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
    find_additional_info_url,
    parse_search_results,
)


_REFERENCE_PATTERN = re.compile(r"\bSWK-\d+\b", re.IGNORECASE)


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _save_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _load_fixture(fixtures_dir: Path, category: str, name: str) -> str:
    fixture_path = fixtures_dir / category / name
    return fixture_path.read_text(encoding="utf-8")


def _write_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        json.dump(payload, handle)
        handle.write("\n")


def _search_postcode_dry(settings: SouthwarkSettings, postcode: str) -> tuple[list[ResultRow], list[str]]:
    if settings.fixtures_dir is None:
        raise ValueError("fixtures_dir must be provided in dry-run mode")
    slug = _slugify(postcode)
    search_dir = settings.fixtures_dir / "search"
    candidates = sorted(search_dir.glob(f"{slug}*.html"))
    if not candidates:
        raise FileNotFoundError(f"No search fixtures for postcode {postcode}")
    rows: list[ResultRow] = []
    html_pages: list[str] = []
    for path in candidates:
        html = path.read_text(encoding="utf-8")
        html_pages.append(html)
        rows.extend(parse_search_results(html, settings.base_url, _REFERENCE_PATTERN))
    return rows, html_pages


def _ensure_snapshot_dirs(settings: SouthwarkSettings) -> tuple[Path, Path, Path]:
    search_dir = settings.output_dir / "search_pages"
    detail_dir = settings.output_dir / "licence_pages"
    additional_dir = settings.output_dir / "additional_pages"
    if settings.snapshot_mode == SnapshotMode.ALL:
        for directory in (search_dir, detail_dir, additional_dir):
            directory.mkdir(parents=True, exist_ok=True)
    return search_dir, detail_dir, additional_dir


def _write_dataset(path: Path, records: list[LicenceRecord]) -> None:
    payload = [record.to_dict() for record in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run(postcodes: Iterable[str], settings: SouthwarkSettings | None = None) -> list[LicenceRecord]:
    """Scrape the Southwark register for the provided postcodes."""

    postcode_list = [item.strip().upper() for item in postcodes if item and item.strip()]
    if not postcode_list:
        return []

    cfg = settings or SouthwarkSettings()
    search_dir, detail_dir, additional_dir = _ensure_snapshot_dirs(cfg)

    json_path = cfg.output_dir / "southwark_licences.json"
    jsonl_path = cfg.output_dir / "southwark_licences.jsonl"
    metadata_path = cfg.output_dir / "metadata.json"

    if cfg.force_refresh:
        for existing in (json_path, jsonl_path, metadata_path):
            if existing.exists():
                existing.unlink()

    if cfg.jsonl_output and jsonl_path.exists():
        jsonl_path.unlink()

    records: list[LicenceRecord] = []
    metadata_entries: list[dict] = []
    seen_refs: set[str] = set()

    def _handle_rows(rows: list[ResultRow], postcode: str, browser) -> None:
        for row in rows:
            if row.reference in seen_refs:
                continue

            if cfg.dry_run:
                assert cfg.fixtures_dir is not None
                detail_html = _load_fixture(cfg.fixtures_dir, "detail", f"{row.reference.lower()}.html")
                detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
                additional_path = cfg.fixtures_dir / "additional" / f"{row.reference.lower()}.html"
                additional_html = additional_path.read_text(encoding="utf-8") if additional_path.exists() else None
                additional_url = find_additional_info_url(detail_soup, row.detail_url)
            else:
                detail_html = fetch_with_retries(
                    browser,
                    row.detail_url,
                    timeout_ms=cfg.timeout_ms,
                    retries=cfg.retries,
                    backoff=cfg.retry_backoff,
                    delay_range=cfg.delay_range,
                )
                detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
                additional_url = find_additional_info_url(detail_soup, row.detail_url)
                additional_html = None
                if additional_url:
                    try:
                        additional_html = fetch_with_retries(
                            browser,
                            additional_url,
                            timeout_ms=cfg.timeout_ms,
                            retries=cfg.retries,
                            backoff=cfg.retry_backoff,
                            delay_range=cfg.delay_range,
                        )
                    except Exception:
                        additional_html = None

            if cfg.snapshot_mode == SnapshotMode.ALL:
                _save_html(detail_dir / f"{row.reference.lower()}.html", detail_html)
                if additional_html:
                    _save_html(additional_dir / f"{row.reference.lower()}.html", additional_html)

            additional_soup = BeautifulSoup(additional_html, SOUP_PARSER) if additional_html else None

            address = extract_address(detail_soup, row.address)
            expiry = extract_expiry(detail_soup)
            licence_type = extract_licence_type(detail_soup) or extract_licence_type(row.summary_text)
            occupancy = extract_occupancy(additional_soup)

            record = LicenceRecord(
                reference=row.reference,
                address=address,
                licence_expiry=expiry,
                licence_type=licence_type,
                occupancy=occupancy,
                detail_url=row.detail_url,
            )

            seen_refs.add(row.reference)
            records.append(record)

            if cfg.jsonl_output:
                _write_jsonl(jsonl_path, record.to_dict())

            metadata_entries.append(
                {
                    "reference": row.reference,
                    "postcode": postcode,
                    "detail_url": row.detail_url,
                    "additional_url": additional_url,
                    "summary": row.summary_text,
                    "captured_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )

            if not cfg.dry_run:
                time.sleep(random.uniform(*cfg.delay_range))

    def _process(browser) -> None:
        for postcode in postcode_list:
            if cfg.dry_run:
                rows, html_pages = _search_postcode_dry(cfg, postcode)
            else:
                rows, html_pages = _search_postcode_live(browser, cfg, postcode)
            if cfg.snapshot_mode == SnapshotMode.ALL:
                for index, html in enumerate(html_pages, start=1):
                    filename = f"{_slugify(postcode)}-{index:04d}.html"
                    _save_html(search_dir / filename, html)
            _handle_rows(rows, postcode, browser)

    if cfg.dry_run:
        _process(None)
    else:
        with BrowserSession(headless=cfg.headless) as browser:
            _process(browser)

    records.sort(key=lambda item: item.reference)

    if cfg.json_output:
        _write_dataset(json_path, records)

    metadata_payload = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "postcodes": postcode_list,
        "records": metadata_entries,
    }
    metadata_path.write_text(json.dumps(metadata_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return records


def _search_postcode_live(
    browser,
    settings: SouthwarkSettings,
    postcode: str,
) -> tuple[list[ResultRow], list[str]]:
    assert not settings.dry_run
    html_pages: list[str] = []
    rows: list[ResultRow] = []
    page = browser.new_page()
    page.set_default_timeout(settings.timeout_ms)
    page.goto(settings.base_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=settings.timeout_ms // 2)
    except TimeoutError:
        pass
    input_locator = page.locator("input[name='search[query]']")
    input_locator.fill(postcode)
    submit = page.locator("form[name='search'] button[type='submit']")
    submit.click()
    time.sleep(random.uniform(*settings.delay_range))
    seen_urls: set[str] = set()
    page_index = 0
    while True:
        page_index += 1
        page.wait_for_timeout(250)
        try:
            page.wait_for_function(
                """
                selector => {
                    const container = document.querySelector(selector);
                    if (!container) {
                        return false;
                    }
                    if (container.querySelector('h2 a')) {
                        return true;
                    }
                    const body = document.body;
                    return body && body.innerText.includes('No results found');
                }
                """,
                arg=settings.result_container_selector,
                timeout=settings.timeout_ms,
            )
        except TimeoutError:
            break
        container_html = page.inner_html(settings.result_container_selector)
        html_pages.append(container_html)
        rows.extend(parse_search_results(container_html, settings.base_url, _REFERENCE_PATTERN))
        if settings.max_pages_per_postcode and page_index >= settings.max_pages_per_postcode:
            break
        current_url = page.url
        if current_url in seen_urls:
            break
        seen_urls.add(current_url)
        next_button = page.locator("a.button", has_text="Next")
        if not next_button.count() or next_button.get_attribute("aria-disabled") == "true":
            break
        with page.expect_navigation(wait_until="domcontentloaded", timeout=settings.timeout_ms):
            next_button.click()
        try:
            page.wait_for_load_state("networkidle", timeout=settings.timeout_ms // 2)
        except TimeoutError:
            pass
        time.sleep(random.uniform(*settings.delay_range))
    page.close()
    return rows, html_pages


