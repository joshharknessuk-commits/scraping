"""Storage helpers for HTML snapshots and datasets."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

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


def ensure_output_paths(output_root: Path) -> OutputPaths:
    search_dir = output_root / "search_pages"
    licence_dir = output_root / "licence_pages"
    additional_dir = output_root / "additional_pages"
    log_dir = output_root / "logs"
    metadata_path = output_root / "metadata.json"
    json_path = output_root / "southwark_licences.json"
    jsonl_path = output_root / "southwark_licences.jsonl"

    for directory in (output_root, search_dir, licence_dir, additional_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return OutputPaths(
        root=output_root,
        search_dir=search_dir,
        licence_dir=licence_dir,
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
    path.write_text(content, encoding="utf-8")


def load_cached_html(path: Path) -> Optional[str]:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def write_dataset(records: Iterable[LicenceRecord], json_path: Path) -> None:
    dataset = [record.to_dict() for record in records]
    json_path.write_text(json.dumps(dataset, indent=2), encoding="utf-8")


def write_metadata(entries: List[dict], path: Path) -> None:
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def append_jsonl_record(path: Path, record: LicenceRecord, lock: Optional[threading.Lock] = None) -> None:
    payload = json.dumps(record.to_dict(), ensure_ascii=False)
    if lock:
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
