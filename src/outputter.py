"""Output helpers for scraping results."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List


def append_jsonl(path: str, obj: dict) -> None:
    """Append a JSON object as a single line to ``path``."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
        fh.write("\n")


def write_json(path: str, rows: List[dict]) -> None:
    """Write a JSON array to ``path``."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)


def append_links_csv(path: str, urls: Iterable[str]) -> None:
    """Append a collection of URLs to a CSV file for resumable scraping."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for url in urls:
            writer.writerow([url])


__all__ = ["append_jsonl", "write_json", "append_links_csv"]
