"""Filesystem helpers with safe, concurrent-friendly writes."""

from __future__ import annotations

import json
import os
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
    licence_dir: Path
    additional_dir: Path
    log_dir: Path
    metadata_path: Path
    json_path: Path
    jsonl_path: Path
    dataset_stem: str


def ensure_output_paths(settings: ScraperSettings) -> OutputPaths:
    dataset_stem = f"{settings.council.slug}_licences"
    root = settings.output_root
    search_dir = root / "search_pages"
    licence_dir = root / "licence_pages"
    additional_dir = root / "additional_pages"
    log_dir = root / "logs"
    metadata_path = root / "metadata.json"
    json_path = root / f"{dataset_stem}.json"
    jsonl_path = root / f"{dataset_stem}.jsonl"

    for directory in (root, search_dir, licence_dir, additional_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return OutputPaths(
        root=root,
        search_dir=search_dir,
        licence_dir=licence_dir,
        additional_dir=additional_dir,
        log_dir=log_dir,
        metadata_path=metadata_path,
        json_path=json_path,
        jsonl_path=jsonl_path,
        dataset_stem=dataset_stem,
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


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp_path.replace(path)


def save_html(path: Path, content: str) -> None:
    _write_text_atomic(path, content)


def load_cached_html(path: Path) -> Optional[str]:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def write_dataset(records: Iterable[LicenceRecord], json_path: Path) -> None:
    dataset = [record.to_dict() for record in records]
    payload = json.dumps(dataset, indent=2, ensure_ascii=False)
    _write_text_atomic(json_path, payload)


def write_metadata(entries: list[dict], path: Path) -> None:
    payload = json.dumps(entries, indent=2, ensure_ascii=False)
    _write_text_atomic(path, payload)


def append_jsonl_record(path: Path, record: LicenceRecord, lock: Optional[threading.Lock] = None) -> None:
    payload = json.dumps(record.to_dict(), ensure_ascii=False)
    if lock:
        with lock:
            _append_line(path, payload)
    else:
        _append_line(path, payload)


def _append_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def write_text(path: Path, text: str) -> None:
    _write_text_atomic(path, text)
