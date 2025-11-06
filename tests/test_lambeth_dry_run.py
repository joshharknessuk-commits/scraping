from __future__ import annotations

import json
from pathlib import Path

from lambeth import Settings, run


def test_lambeth_dry_run(tmp_path: Path) -> None:
    output_root = tmp_path / "artefacts"
    settings = Settings(dry_run=True, output_root=output_root)

    records = run(["SW9 0AA"], settings=settings)

    dataset_path = output_root / "lambeth" / "lambeth_licences.json"
    metadata_path = output_root / "lambeth" / "metadata.json"

    assert dataset_path.exists()
    assert metadata_path.exists()

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    entry = data[0]
    assert entry["reference"] == "LMB-0001"
    assert entry["address"] == "12 Sample Road, London SW9 0AA"

    assert len(records) == 1
    assert records[0].occupancy == 3

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata[0]["reference"] == "LMB-0001"
    assert metadata[0]["occupancy"] == 3
