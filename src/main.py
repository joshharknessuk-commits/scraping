"""Command line entry point for the Southwark landlord licence scraper."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import requests

from . import config
from .detail_parser import (
    fetch_additional,
    fetch_detail,
    parse_additional_html_for_occupancy,
    parse_detail_html,
)
from .outputter import append_jsonl, append_links_csv, write_json
from .playwright_capture import capture_and_save_cookies
from .searcher import iterate_all_detail_links
from .sessioner import load_playwright_cookies_into_session, make_session, warmup
from .utils import now_iso, normalize_detail_url


def _load_existing_records(path: str) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    file_path = Path(path)
    if not file_path.exists():
        return records
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _detect_captcha(html: str) -> bool:
    lowered = html.lower()
    return "recaptcha" in lowered or "g-recaptcha" in lowered or "h-captcha" in lowered


def build_additional_url(detail_url: str) -> str:
    if detail_url.endswith(config.ADDITIONAL_SUFFIX):
        return detail_url
    appended = detail_url.rstrip("/") + config.ADDITIONAL_SUFFIX
    return normalize_detail_url(appended)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Southwark landlord licence records")
    parser.add_argument("--postcode", required=True, help="Postcode or search query to filter licences")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to crawl")
    parser.add_argument("--resume", action="store_true", help="Resume from previously scraped records")
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Launch Playwright to capture cookies after solving the CAPTCHA manually",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    Path(config.OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)

    session = make_session()

    if args.use_playwright:
        capture_and_save_cookies(config.COOKIES_FILE)
        load_playwright_cookies_into_session(session, config.COOKIES_FILE)
    warmup(session)

    existing_records: List[Dict[str, object]] = []
    existing_urls: Set[str] = set()
    if args.resume:
        existing_records = _load_existing_records(config.OUTPUT_JSONL)
        for record in existing_records:
            url = record.get("url_detail")
            if isinstance(url, str):
                existing_urls.add(normalize_detail_url(url))
        print(f"Loaded {len(existing_records)} existing records for resume mode")

    print("Collecting detail links...")
    detail_links = list(
        iterate_all_detail_links(
            session,
            query=args.postcode,
            start_page=1,
            max_pages=args.max_pages,
        )
    )
    if detail_links:
        append_links_csv(config.LINKS_CSV, detail_links)
    print(f"Discovered {len(detail_links)} detail pages")

    results: List[Dict[str, object]] = list(existing_records)
    total_new = 0
    for index, detail_url in enumerate(detail_links, start=1):
        normalized_detail = normalize_detail_url(detail_url)
        if normalized_detail in existing_urls:
            print(f"[{index}/{len(detail_links)}] {normalized_detail} SKIP existing")
            continue
        try:
            detail_html = fetch_detail(session, normalized_detail)
        except requests.RequestException as exc:
            print(f"[{index}/{len(detail_links)}] {normalized_detail} ERROR detail: {exc}")
            continue
        if not args.use_playwright and _detect_captcha(detail_html):
            print(
                "CAPTCHA detected in response. Re-run with --use-playwright to capture cookies."
            )
            return 1
        detail_data = parse_detail_html(detail_html)
        time.sleep(config.RATE_LIMIT_SECONDS)
        additional_url = build_additional_url(normalized_detail)
        try:
            additional_html = fetch_additional(session, additional_url)
        except requests.RequestException as exc:
            print(f"[{index}/{len(detail_links)}] {normalized_detail} ERROR additional: {exc}")
            continue
        if not args.use_playwright and _detect_captcha(additional_html):
            print(
                "CAPTCHA detected in additional-info response. Re-run with --use-playwright."
            )
            return 1
        occupancy = parse_additional_html_for_occupancy(additional_html)
        time.sleep(config.RATE_LIMIT_SECONDS)

        record = {
            "council": config.COUNCIL,
            "address": detail_data.get("address"),
            "licence_type": detail_data.get("licence_type"),
            "occupancy": occupancy,
            "end_date": detail_data.get("end_date"),
            "licence_reference": detail_data.get("licence_reference"),
            "url_detail": normalized_detail,
            "url_additional": additional_url,
            "scraped_at": now_iso(),
        }
        append_jsonl(config.OUTPUT_JSONL, record)
        results.append(record)
        existing_urls.add(normalized_detail)
        total_new += 1
        print(f"[{index}/{len(detail_links)}] {record.get('licence_reference') or normalized_detail} OK")

    write_json(config.OUTPUT_JSON, results)
    print(f"Scraped {total_new} new licences; total records now {len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
