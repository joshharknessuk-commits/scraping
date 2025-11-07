"""Concurrent scraper for the Lambeth Metastreet public register.

This script drives the Metastreet-powered register with Patchright (stealth
Playwright) to capture licence metadata. It is optimised for large runs (18k+
records) by using two worker threads that each maintain their own browser
context.

Usage::

    python lambeth_metastreet_scraper.py --postcodes lambeth_postcodes.txt \
        --output data/lambeth/metastreet_licences.csv

The scraper writes every captured licence to the CSV immediately, supports
resuming by skipping existing references, and logs progress with timestamps.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from bs4 import BeautifulSoup
from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from lambeth_scraper.browser import BrowserEnv
from lambeth_scraper.config import (
    COUNCIL_NAME,
    DEFAULT_POSTCODES_PATH,
    Settings,
    SnapshotMode,
    SOUP_PARSER,
)
from lambeth_scraper.fetch import fetch_pages
from lambeth_scraper.parse_lambeth import (
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
)
from lambeth_scraper.search_flow import search_postcode

CSV_FIELDNAMES = (
    "reference",
    "licence_end_date",
    "occupancy",
    "licence_type",
    "address",
    "council",
    "detail_url",
    "captured_at",
)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_postcodes(path: Path, limit: Optional[int] = None) -> list[str]:
    contents = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            postcode = line.strip()
            if not postcode or postcode.startswith("#"):
                continue
            contents.append(postcode)
            if limit is not None and len(contents) >= limit:
                break
    return contents


class CsvWriter:
    """Thread-safe CSV writer that retries when persistence fails."""

    def __init__(self, path: Path, logger: logging.Logger, retries: int = 3) -> None:
        self.path = path
        self.logger = logger
        self.retries = max(1, retries)
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = False
        self.existing_refs = self._load_existing_refs()

    def _load_existing_refs(self) -> set[str]:
        if not self.path.exists():
            self._header_written = False
            return set()

        references: set[str] = set()
        try:
            with self.path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self._header_written = reader.fieldnames is not None
                for row in reader:
                    reference = (row.get("reference") or "").strip().upper()
                    if reference:
                        references.add(reference)
        except csv.Error as exc:
            self.logger.warning("Failed reading existing CSV: %s", exc)
            self._header_written = False
            return set()
        return references

    def write(self, row: dict[str, object]) -> None:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                with self.lock:
                    with self.path.open("a", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
                        if not self._header_written:
                            writer.writeheader()
                            handle.flush()
                            os.fsync(handle.fileno())
                            self._header_written = True
                        writer.writerow(row)
                        handle.flush()
                        os.fsync(handle.fileno())
                return
            except OSError as exc:
                last_error = exc
                self.logger.warning(
                    "CSV write attempt %s/%s failed: %s", attempt, self.retries, exc
                )
                backoff = min(8, 2 ** (attempt - 1))
                time.sleep(backoff)
        if last_error:
            raise last_error


@dataclass(slots=True)
class ScraperStats:
    logger: logging.Logger
    total_captured: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def increment(self) -> int:
        with self._lock:
            self.total_captured += 1
            return self.total_captured


class ReferenceRegistry:
    """Track processed references and prevent duplicates."""

    def __init__(self, initial: Iterable[str] | None = None) -> None:
        self._references = set(item.upper() for item in (initial or []))
        self._lock = threading.Lock()

    def register(self, reference: str) -> bool:
        normalised = reference.strip().upper()
        if not normalised:
            return False
        with self._lock:
            if normalised in self._references:
                return False
            self._references.add(normalised)
            return True


def create_settings(args: argparse.Namespace) -> Settings:
    return Settings(
        headless=not args.headed,
        timeout_ms=args.timeout,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        retries=args.retries,
        retry_base_delay=args.retry_backoff,
        snapshot_mode=SnapshotMode.NONE,
        concurrency=args.workers,
        seed=args.seed,
    )


def process_postcode(
    env: BrowserEnv,
    postcode: str,
    settings: Settings,
    csv_writer: CsvWriter,
    registry: ReferenceRegistry,
    stats: ScraperStats,
) -> None:
    logger = stats.logger
    logger.info("Worker %s searching postcode %s", threading.current_thread().name, postcode)

    def _noop_save(_: str, __: int, ___: str) -> None:
        return None

    try:
        rows = search_postcode(env, postcode, settings, _noop_save)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logger.error("Postcode %s failed due to browser error: %s", postcode, exc)
        return
    except Exception as exc:  # noqa: BLE001 - defensive catch to keep workers alive
        logger.exception("Unexpected error processing postcode %s: %s", postcode, exc)
        return

    if not rows:
        logger.info("Postcode %s returned no licences", postcode)
        return

    logger.info("Postcode %s yielded %s licence candidates", postcode, len(rows))

    for row in rows:
        reference = row.reference.strip().upper()
        if not reference:
            logger.debug("Skipping row with empty reference for postcode %s", postcode)
            continue
        if not registry.register(reference):
            logger.debug("Skipping duplicate licence %s", reference)
            continue

        detail_html: Optional[str]
        additional_html: Optional[str]
        try:
            detail_html, additional_html, _ = fetch_pages(
                env,
                reference,
                row.detail_url,
                settings,
                cache_paths={},
                force=True,
            )
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            logger.warning("Failed fetching pages for %s: %s", reference, exc)
            continue

        if not detail_html:
            logger.warning("Missing detail HTML for %s", reference)
            continue

        detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
        additional_soup = BeautifulSoup(additional_html, SOUP_PARSER) if additional_html else None

        record = {
            "reference": reference,
            "licence_end_date": extract_expiry(detail_soup),
            "occupancy": extract_occupancy(additional_soup),
            "licence_type": extract_licence_type(detail_soup),
            "address": extract_address(detail_soup) or row.address,
            "council": COUNCIL_NAME,
            "detail_url": row.detail_url,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            csv_writer.write(record)
        except OSError as exc:
            logger.error("Failed to persist record for %s: %s", reference, exc)
            continue

        count = stats.increment()

        logger.info(
            "Captured licence %s (#%s) - address=%s, expiry=%s",
            reference,
            count,
            record["address"],
            record["licence_end_date"],
        )
        logger.info("Wrote licence %s to %s (total=%s)", reference, csv_writer.path, count)


def worker_loop(
    worker_id: int,
    postcodes_iter: Iterator[str],
    iterator_lock: threading.Lock,
    settings: Settings,
    csv_writer: CsvWriter,
    registry: ReferenceRegistry,
    stats: ScraperStats,
) -> None:
    logger = stats.logger
    logger.info("Worker %s initialised", worker_id + 1)
    with BrowserEnv(settings, logger) as env:
        while True:
            with iterator_lock:
                try:
                    postcode = next(postcodes_iter)
                except StopIteration:
                    break
            process_postcode(env, postcode, settings, csv_writer, registry, stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Lambeth licences from Metastreet")
    parser.add_argument(
        "--postcodes",
        type=Path,
        default=DEFAULT_POSTCODES_PATH,
        help="Path to newline-delimited postcodes (default: lambeth_postcodes.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/lambeth/metastreet_licences.csv"),
        help="Destination CSV path",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of concurrent workers (default: 2)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionally limit the number of postcodes processed",
    )
    parser.add_argument("--headed", action="store_true", help="Run browsers in headed mode")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30_000,
        help="Navigation timeout in milliseconds",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.75,
        help="Minimum delay between requests to mimic human browsing",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=1.5,
        help="Maximum delay between requests to mimic human browsing",
    )
    parser.add_argument("--retries", type=int, default=3, help="Browser retry attempts")
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=1.0,
        help="Base delay (seconds) for retry backoff",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for shuffling postcodes")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging with timestamps",
    )

    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    configure_logging(args.verbose)
    logger = logging.getLogger("lambeth.metastreet")

    postcodes = load_postcodes(args.postcodes, limit=args.limit)
    if not postcodes:
        logger.error("No postcodes loaded from %s", args.postcodes)
        raise SystemExit(1)

    if args.seed is not None:
        import random

        rng = random.Random(args.seed)
        rng.shuffle(postcodes)

    settings = create_settings(args)

    csv_writer = CsvWriter(args.output, logger)
    registry = ReferenceRegistry(csv_writer.existing_refs)
    stats = ScraperStats(logger=logger)

    logger.info(
        "Starting scrape with %s workers across %s postcodes (already have %s references)",
        args.workers,
        len(postcodes),
        len(csv_writer.existing_refs),
    )

    iterator_lock = threading.Lock()
    postcodes_iter = iter(postcodes)

    threads = []
    for index in range(args.workers):
        thread = threading.Thread(
            target=worker_loop,
            name=f"worker-{index + 1}",
            args=(
                index,
                postcodes_iter,
                iterator_lock,
                settings,
                csv_writer,
                registry,
                stats,
            ),
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    logger.info("Scrape complete. Captured %s new licences.", stats.total_captured)


if __name__ == "__main__":
    main()

