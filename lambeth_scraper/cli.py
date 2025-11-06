"""Command-line interface for the Lambeth scraper."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import (
    DEFAULT_ACCESS_DENIED_BACKOFF,
    DEFAULT_ACCESS_DENIED_RETRIES,
    DEFAULT_DELAY_RANGE,
    DEFAULT_POSTCODES_PATH,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_TIMEOUT_MS,
    Settings,
    SnapshotMode,
)
from .runner import run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium in headed mode (default headless).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help="Page timeout in milliseconds (default: %(default)s).",
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
        default=DEFAULT_DELAY_RANGE[0],
        help="Minimum delay between actions in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=DEFAULT_DELAY_RANGE[1],
        help="Maximum delay between actions in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent browser workers (default: %(default)s).",
    )
    parser.add_argument(
        "--refresh-interval",
        type=int,
        default=DEFAULT_REFRESH_INTERVAL,
        help="Re-run the search flow after this many successful captures (0 disables).",
    )
    parser.add_argument(
        "--access-denied-retries",
        type=int,
        default=DEFAULT_ACCESS_DENIED_RETRIES,
        help="Retry a licence this many times when the site responds with Access Denied.",
    )
    parser.add_argument(
        "--access-denied-backoff",
        type=float,
        default=DEFAULT_ACCESS_DENIED_BACKOFF,
        help="Seconds to wait (multiplied by attempt count) before retrying after Access Denied.",
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
        help="Stream results to lambeth_licences.jsonl as each licence is captured.",
    )
    parser.add_argument(
        "--no-json-array",
        action="store_true",
        help="Skip writing the final JSON array file (json-only mode disables by default).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (name or integer, default INFO).",
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


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    postcodes_file = Path(args.postcodes_file).resolve()
    postcodes = read_postcodes(postcodes_file)

    output_root = Path(args.out_dir).resolve() if args.out_dir else Settings().output_root

    settings = Settings(
        output_root=output_root,
        headless=not args.headed,
        timeout_ms=args.timeout_ms,
        max_pagination_pages=args.max_pages,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        force_refresh=args.force,
        log_level=parse_log_level(args.log_level),
        snapshot_mode=SnapshotMode(args.snapshot_mode),
        seed=args.seed,
        concurrency=max(args.concurrency, 1),
        jsonl_output=args.jsonl_output,
        json_array_output=not args.no_json_array,
        refresh_interval=max(args.refresh_interval, 0),
        access_denied_retries=args.access_denied_retries,
        access_denied_backoff=max(args.access_denied_backoff, 0.0),
    )

    print(
        "Scraping %s postcodes from %s to %s (headless=%s, force=%s, snapshots=%s, concurrency=%s, jsonl=%s, refresh_interval=%s)"
        % (
            len(postcodes),
            postcodes_file,
            settings.output_root,
            settings.headless,
            settings.force_refresh,
            settings.snapshot_mode.value,
            settings.concurrency,
            settings.jsonl_output,
            settings.refresh_interval,
        ),
    )

    records = run(postcodes, settings)

    print("Finished scraping %s records; outputs written to %s" % (len(records), settings.output_root))


if __name__ == "__main__":
    main()
