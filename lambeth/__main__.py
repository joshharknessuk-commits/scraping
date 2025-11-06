from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape the Lambeth HMO register")
    parser.add_argument("postcodes", nargs="*", help="Postcodes to scrape; defaults to bundled list")
    parser.add_argument("--dry-run", action="store_true", help="Use local fixtures instead of live requests")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data"),
        help="Root directory for output artefacts",
    )
    args = parser.parse_args()

    settings = Settings(dry_run=args.dry_run, output_root=args.output_root)
    records = run(args.postcodes or None, settings=settings)
    print(f"Captured {len(records)} Lambeth licences")


if __name__ == "__main__":
    main()
