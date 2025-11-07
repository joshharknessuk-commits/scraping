"""Command-line interface for the Southwark scraper."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .config import (
    DEFAULT_DELAY_RANGE,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_TIMEOUT_MS,
    SnapshotMode,
    SouthwarkSettings,
    load_postcodes,
)
from .scraper import run


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape the Southwark landlord licence register into JSON and JSONL outputs.",
    )
    parser.add_argument(
        "--postcodes-file",
        type=Path,
        default=Path("southwark_postcodes.txt"),
        help="Path to a newline-delimited postcode list.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for JSON/JSONL outputs and optional HTML snapshots.",
    )
    parser.add_argument("--headed", action="store_true", help="Run Chromium in headed mode.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help="Page load timeout in milliseconds (default: 30000).",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=DEFAULT_DELAY_RANGE[0],
        help="Minimum delay between actions in seconds (default: 0.75).",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=DEFAULT_DELAY_RANGE[1],
        help="Maximum delay between actions in seconds (default: 1.5).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional pagination cap per postcode.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="Retry attempts for individual page fetches (default: 3).",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF,
        help="Seconds added per retry attempt (default: 1.5).",
    )
    parser.add_argument(
        "--snapshot-mode",
        choices=[mode.value for mode in SnapshotMode],
        default=SnapshotMode.NONE.value,
        help="Write HTML snapshots: none (default) or all.",
    )
    parser.add_argument(
        "--no-jsonl",
        action="store_true",
        help="Disable streaming JSONL output (enabled by default).",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable the aggregated JSON array output (enabled by default).",
    )
    parser.add_argument("--force", action="store_true", help="Force refresh all pages and outputs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load HTML fixtures from tests/fixtures instead of hitting the live website.",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=None,
        help="Optional override for the dry-run fixtures directory.",
    )
    return parser.parse_args(argv)


def build_settings(args: argparse.Namespace) -> SouthwarkSettings:
    return SouthwarkSettings(
        output_dir=args.out_dir,
        headless=not args.headed,
        timeout_ms=args.timeout_ms,
        delay_range=(max(args.min_delay, 0.0), max(args.max_delay, args.min_delay)),
        max_pages_per_postcode=args.max_pages,
        retries=max(args.retries, 1),
        retry_backoff=max(args.retry_backoff, 0.1),
        snapshot_mode=SnapshotMode(args.snapshot_mode),
        jsonl_output=not args.no_jsonl,
        json_output=not args.no_json,
        force_refresh=args.force,
        dry_run=args.dry_run,
        fixtures_dir=args.fixtures_dir,
    )


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    settings = build_settings(args)
    postcodes = load_postcodes(args.postcodes_file)
    records = run(postcodes, settings)
    print(
        "Captured %s Southwark licences from %s postcodes. Outputs in %s"
        % (len(records), len(postcodes), settings.output_dir)
    )


if __name__ == "__main__":  # pragma: no cover
    main()
