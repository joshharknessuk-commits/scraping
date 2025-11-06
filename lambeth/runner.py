"""Lambeth scraper entry point."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List

from common.orchestrator import CouncilSpec, run_scraper
from common.models import LicenceRecord

from .config import (
    COUNCIL_NAME,
    DATASET_BASENAME,
    DEFAULT_POSTCODES_PATH,
    RESULT_LINK_PATTERN,
    Settings,
    SnapshotMode,
)
from .parse import (
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
    find_additional_info_url,
    parse_search_results,
)
from .search import search_postcode


SPEC = CouncilSpec(
    name=COUNCIL_NAME,
    dataset_basename=DATASET_BASENAME,
    reference_pattern=RESULT_LINK_PATTERN,
    search_postcode=search_postcode,
    parse_search_results=parse_search_results,
    extract_address=extract_address,
    extract_expiry=extract_expiry,
    extract_licence_type=extract_licence_type,
    extract_occupancy=extract_occupancy,
    resolve_additional_url=find_additional_info_url,
)


def run(postcodes: Iterable[str], settings: Settings | None = None) -> List[LicenceRecord]:
    actual_settings = settings or Settings()
    return run_scraper(postcodes, actual_settings, SPEC)


def main(argv: list[str] | None = None) -> None:
    defaults = Settings()
    parser = argparse.ArgumentParser(description="Scrape the Lambeth landlord licence register.")
    parser.add_argument(
        "--postcodes-file",
        default=str(DEFAULT_POSTCODES_PATH),
        help="Path to postcode list (one per line).",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory for output dataset and HTML snapshots.",
    )
    parser.add_argument("--headed", action="store_true", help="Run Chromium in headed mode (default headless).")
    parser.add_argument("--timeout-ms", type=int, default=defaults.timeout_ms)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--min-delay", type=float, default=defaults.min_delay)
    parser.add_argument("--max-delay", type=float, default=defaults.max_delay)
    parser.add_argument("--concurrency", type=int, default=defaults.concurrency)
    parser.add_argument("--refresh-interval", type=int, default=defaults.refresh_interval or 0)
    parser.add_argument("--access-denied-retries", type=int, default=defaults.access_denied_retries)
    parser.add_argument("--access-denied-backoff", type=float, default=defaults.access_denied_backoff)
    parser.add_argument("--force", action="store_true", help="Force refetch of HTML even if cached files exist.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--snapshot-mode",
        choices=[mode.value for mode in SnapshotMode],
        default=SnapshotMode.NONE.value,
    )
    parser.add_argument("--jsonl-output", action="store_true")
    parser.add_argument("--no-json-array", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--dry-run", action="store_true", help="Use fixture HTML instead of live scraping.")
    parser.add_argument(
        "--fixture-dir",
        default=None,
        help="Directory containing fixture HTML when running in dry-run mode.",
    )

    args = parser.parse_args(argv)

    postcodes_path = Path(args.postcodes_file).resolve()
    postcodes = _read_postcodes(postcodes_path)

    output_root = Path(args.out_dir).resolve() if args.out_dir else defaults.output_root
    fixture_dir = Path(args.fixture_dir).resolve() if args.fixture_dir else None

    settings = Settings(
        output_root=output_root,
        headless=not args.headed,
        timeout_ms=args.timeout_ms,
        max_pagination_pages=args.max_pages,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        force_refresh=args.force,
        log_level=_parse_log_level(args.log_level),
        snapshot_mode=SnapshotMode(args.snapshot_mode),
        seed=args.seed,
        concurrency=max(args.concurrency, 1),
        jsonl_output=args.jsonl_output,
        json_array_output=not args.no_json_array,
        refresh_interval=max(args.refresh_interval, 0),
        access_denied_retries=max(args.access_denied_retries, 1),
        access_denied_backoff=max(args.access_denied_backoff, 0.0),
        dry_run=args.dry_run,
        fixture_dir=fixture_dir,
    )

    records = run(postcodes, settings)
    print(f"Finished scraping {len(records)} records; outputs written to {settings.output_root}")


def _read_postcodes(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Postcodes file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _parse_log_level(value: str) -> int:
    if value.isdigit():
        return int(value)
    level = getattr(logging, value.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {value}")
    return level


if __name__ == "__main__":
    main()
