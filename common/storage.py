"""Storage helpers shared by the council scrapers."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Optional

from .models import LicenceRecord, ScrapePaths


def ensure_output_paths(output_root: Path, dataset_basename: str) -> ScrapePaths:
    """Create the required directory structure for scraper artefacts."""

    search_dir = output_root / "search_pages"
    licence_dir = output_root / "licence_pages"
    additional_dir = output_root / "additional_pages"
    log_dir = output_root / "logs"
    json_path = output_root / f"{dataset_basename}.json"
    jsonl_path = output_root / f"{dataset_basename}.jsonl"
    metadata_path = output_root / "metadata.json"

    for directory in (output_root, search_dir, licence_dir, additional_dir, log_dir):
        os.makedirs(directory, exist_ok=True)

    return ScrapePaths(
        root=output_root,
        search_dir=search_dir,
        licence_dir=licence_dir,
        additional_dir=additional_dir,
        json_path=json_path,
        jsonl_path=jsonl_path,
        metadata_path=metadata_path,
        log_dir=log_dir,
    )


def slugify_for_filename(value: str) -> str:
    safe = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            safe.append(char)
        else:
            safe.append("-")
    result = "".join(safe).strip("-")
    return result or "entry"


def save_html(path: Path, content: str) -> None:
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_cached_html(path: Path) -> Optional[str]:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def write_dataset(records: Iterable[LicenceRecord], json_path: Path) -> None:
    payload = [asdict(record) for record in records]
    os.makedirs(json_path.parent, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_metadata(entries: list[dict], path: Path) -> None:
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2, ensure_ascii=False)


def append_jsonl_record(path: Path, record: LicenceRecord, lock: Optional[threading.Lock] = None) -> None:
    payload = json.dumps(asdict(record), ensure_ascii=False)
    os.makedirs(path.parent, exist_ok=True)

    if lock is not None:
        with lock:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
    else:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
