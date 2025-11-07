"""Disk persistence helpers shared between scrapers."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .config import ScraperSettings
from .models import LicenceRecord


@dataclass(slots=True)
class OutputPaths:
    root: Path
    search_dir: Path
    detail_dir: Path
    additional_dir: Path
    log_dir: Path
    metadata_path: Path
    json_path: Path
    jsonl_path: Path


def build_output_paths(settings: ScraperSettings) -> OutputPaths:
    """Prepare the directory structure for the active scraper."""

    root = settings.council_output_root()
    search_dir = root / "search_pages"
    detail_dir = root / "licence_pages"
    additional_dir = root / "additional_pages"
    log_dir = root / "logs"
    metadata_path = root / "metadata.json"
    json_path = root / settings.dataset_filename()
    jsonl_path = root / settings.jsonl_filename()

    for directory in (root, search_dir, detail_dir, additional_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return OutputPaths(
        root=root,
        search_dir=search_dir,
        detail_dir=detail_dir,
        additional_dir=additional_dir,
        log_dir=log_dir,
        metadata_path=metadata_path,
        json_path=json_path,
        jsonl_path=jsonl_path,
    )


def slugify_for_filename(value: str) -> str:
    safe = []
    for char in value.lower():
        if char.isalnum():
            safe.append(char)
        elif char in {"-", "_"}:
            safe.append(char)
        else:
            safe.append("-")
    result = "".join(safe).strip("-")
    return result or "entry"


def save_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_cached_html(path: Path) -> Optional[str]:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def write_dataset(records: Iterable[LicenceRecord], json_path: Path) -> None:
    dataset = [record.to_dict() for record in records]
    write_json(json_path, dataset)


def write_metadata(entries: list[dict], path: Path) -> None:
    write_json(path, entries)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def append_jsonl_record(path: Path, record: LicenceRecord, lock: Optional[threading.Lock] = None) -> None:
    payload = json.dumps(record.to_dict(), ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if lock:
        with lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
    else:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
