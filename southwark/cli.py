"""Command-line entry for the Southwark scraper."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

from common.config import ScraperSettings

from .config import (
    DEFAULT_POSTCODES_PATH,
    DEFAULT_OUTPUT_ROOT,
    Settings,
    SnapshotMode,
)
from .runner import run


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape the Southwark landlord licence register.")
    parser.add_argument(
        "--postcodes-file",
        default=str(DEFAULT_POSTCODES_PATH),
        help="Path to postcode list (one per line).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory for output dataset and HTML snapshots.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium in headed mode (default headless).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="Page timeout in milliseconds (default: 30000).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit pagination per postcode (default unlimited).",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=None,
        help="Minimum delay between actions in seconds (default: 0.75).",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=None,
        help="Maximum delay between actions in seconds (default: 1.5).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent browser workers (default: 1).",
    )
    parser.add_argument(
        "--refresh-interval",
        type=int,
        default=None,
        help="Re-run the search flow after this many successful captures (0 disables).",
    )
    parser.add_argument(
        "--access-denied-retries",
        type=int,
        default=None,
        help="Retry a licence this many times when the site responds with Access Denied.",
    )
    parser.add_argument(
        "--access-denied-backoff",
        type=float,
        default=None,
        help="Seconds to wait (multiplied by attempt count) before retry after Access Denied.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refetch of HTML even if cached files exist.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed to shuffle postcode order reproducibly.",
    )
    parser.add_argument(
        "--snapshot-mode",
        choices=[mode.value for mode in SnapshotMode],
        default=SnapshotMode.NONE.value,
        help="HTML snapshot persistence: none (default) or all.",
    )
    parser.add_argument(
        "--jsonl-output",
        action="store_true",
        help="Stream results to <council>_licences.jsonl as each licence is captured.",
    )
    parser.add_argument(
        "--no-json-array",
        action="store_true",
        help="Skip writing the final JSON array file.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (name or integer, default INFO).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load HTML from tests/fixtures instead of hitting the live site.",
    )
    parser.add_argument(
        "--mock-data-dir",
        default=None,
        help="Override the directory containing dry-run fixture HTML.",
    )
    return parser.parse_args(argv)


def read_postcodes(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Postcodes file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def parse_log_level(value: str) -> int:
    if value.isdigit():
        return int(value)
    level = getattr(logging, value.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {value}")
    return level


def build_settings(args: argparse.Namespace) -> ScraperSettings:
    kwargs = {
        "output_root": Path(args.out_dir),
        "headless": not args.headed,
        "force_refresh": args.force,
        "log_level": parse_log_level(args.log_level),
        "snapshot_mode": SnapshotMode(args.snapshot_mode),
        "seed": args.seed,
        "concurrency": max(args.concurrency, 1),
        "jsonl_output": args.jsonl_output,
        "json_array_output": not args.no_json_array,
        "dry_run": args.dry_run,
        "mock_data_dir": Path(args.mock_data_dir) if args.mock_data_dir else None,
    }
    if args.timeout_ms is not None:
        kwargs["timeout_ms"] = args.timeout_ms
    if args.max_pages is not None:
        kwargs["max_pagination_pages"] = max(args.max_pages, 1)
    if args.min_delay is not None:
        kwargs["min_delay"] = max(args.min_delay, 0.0)
    if args.max_delay is not None:
        kwargs["max_delay"] = max(args.max_delay, kwargs.get("min_delay", args.max_delay))
    if args.refresh_interval is not None:
        kwargs["refresh_interval"] = max(args.refresh_interval, 0)
    if args.access_denied_retries is not None:
        kwargs["access_denied_retries"] = max(args.access_denied_retries, 1)
    if args.access_denied_backoff is not None:
        kwargs["access_denied_backoff"] = max(args.access_denied_backoff, 0.0)
    return Settings(**kwargs)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)

    postcodes_file = Path(args.postcodes_file).resolve()
    postcodes = read_postcodes(postcodes_file)

    settings = build_settings(args)

    print(
        "Scraping %s postcodes from %s to %s (headless=%s, force=%s, snapshots=%s, concurrency=%s, jsonl=%s, dry_run=%s)"
        % (
            len(postcodes),
            postcodes_file,
            settings.output_root,
            settings.headless,
            settings.force_refresh,
            settings.snapshot_mode.value,
            settings.concurrency,
            settings.jsonl_output,
            settings.dry_run,
        ),
    )

    records = run(postcodes, settings)

    print("Finished scraping %s records; outputs written to %s" % (len(records), settings.output_root))


if __name__ == "__main__":  # pragma: no cover
    main()
