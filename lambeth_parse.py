"""
Parse saved Lambeth licence HTML pages into a structured JSON dataset.

The script relies on HTML files captured by ``lambeth_fetch.py`` and extracts
key attributes using Beautiful Soup. The resulting dataset is stored as JSON so
it can be imported into the wider housing data pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from lambeth_scraper.config import SOUP_PARSER

from lambeth_scraper.parse_lambeth import (
    extract_address as scrape_extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy as scrape_extract_occupancy,
)

SCRAPE_ROOT = Path(__file__).resolve().parent
DATA_ROOT = SCRAPE_ROOT / "data" / "lambeth"
LOG_DIR = DATA_ROOT / "logs"
METADATA_PATH = DATA_ROOT / "metadata.json"
OUTPUT_PATH = DATA_ROOT / "lambeth_licences.json"


def configure_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("lambeth.parse")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / "parse.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def load_metadata() -> List[Dict]:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_PATH}")
    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_reference(soup: BeautifulSoup) -> Optional[str]:
    pattern = re.compile(r"[A-Z]{3}-\d+", re.IGNORECASE)
    for text in soup.stripped_strings:
        match = pattern.search(text)
        if match:
            return match.group().upper()
    return None


def parse_record(entry: Dict, base_dir: Path, logger: logging.Logger) -> Optional[Dict]:
    detail_relpath = entry.get("detail_html")
    if not detail_relpath:
        logger.warning("No detail HTML path recorded for %s", entry.get("detail_url"))
        return None
    detail_path = base_dir / detail_relpath
    additional_relpath = entry.get("additional_html")
    additional_path = base_dir / additional_relpath if additional_relpath else None

    try:
        detail_html = detail_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Missing detail HTML for %s", entry.get("detail_url"))
        return None
    detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)

    try:
        additional_html = (
            additional_path.read_text(encoding="utf-8") if additional_path else None
        )
    except FileNotFoundError:
        logger.warning("Missing additional info HTML for %s", entry.get("detail_url"))
        additional_html = None
    additional_soup = BeautifulSoup(additional_html, SOUP_PARSER) if additional_html else None

    reference = find_reference(detail_soup)
    if not reference:
        logger.warning("Unable to locate licence reference for %s", entry.get("detail_url"))
        return None

    address = scrape_extract_address(detail_soup) or entry.get("address_hint")
    licence_expiry = extract_expiry(detail_soup)
    licence_type = extract_licence_type(detail_soup)
    occupancy = scrape_extract_occupancy(additional_soup)

    return {
        "council": "Lambeth",
        "reference": reference,
        "address": address,
        "occupancy": occupancy,
        "licence_expiry": licence_expiry,
        "licence_type": licence_type,
        "detail_url": entry.get("detail_url"),
    }


def run_parser() -> None:
    logger = configure_logger()
    metadata = load_metadata()

    records: Dict[str, Dict] = {}
    skipped = 0

    for entry in metadata:
        record = parse_record(entry, DATA_ROOT, logger)
        if not record:
            skipped += 1
            continue
        reference = record["reference"]
        if reference in records:
            logger.info("Duplicate reference %s encountered; keeping first occurrence", reference)
            continue
        records[reference] = record

    dataset = sorted(records.values(), key=lambda item: item["reference"])
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    logger.info(
        "Parsed %s records (skipped %s). Output written to %s",
        len(dataset),
        skipped,
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    run_parser()
