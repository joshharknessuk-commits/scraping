from __future__ import annotations

import json
from pathlib import Path

from southwark.config import Settings, SnapshotMode
from southwark.runner import run


def test_southwark_dry_run(tmp_path: Path) -> None:
    settings = Settings(
        output_root=tmp_path,
        dry_run=True,
        snapshot_mode=SnapshotMode.ALL,
        jsonl_output=True,
    )

    records = run(["SE1 0AA"], settings)

    dataset_path = tmp_path / "southwark_licences.json"
    assert dataset_path.exists(), "JSON dataset should be written"

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    entry = data[0]
    assert entry["reference"] == "SWK-000001"
    assert entry["address"] == "123 Example Street, London SE1 0AA"
    assert entry["occupancy"] == 5
    assert entry["licence_expiry"] == "2025-12-31"

    metadata_path = tmp_path / "metadata.json"
    assert metadata_path.exists()

    jsonl_path = tmp_path / "southwark_licences.jsonl"
    assert jsonl_path.exists()
    jsonl_entries = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(jsonl_entries) == 1

    search_snapshot = tmp_path / "search_pages" / "se1-0aa-0001.html"
    assert search_snapshot.exists()
    detail_snapshot = tmp_path / "licence_pages" / "swk-000001.html"
    assert detail_snapshot.exists()
    additional_snapshot = tmp_path / "additional_pages" / "swk-000001.html"
    assert additional_snapshot.exists()
