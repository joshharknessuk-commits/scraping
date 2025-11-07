from __future__ import annotations

import json
from pathlib import Path

from southwark import Settings, run


def test_southwark_dry_run(tmp_path: Path) -> None:
    output_root = tmp_path / "artefacts"
    settings = Settings(dry_run=True, output_root=output_root)

    records = run(["SE1 0AA"], settings=settings)

    dataset_path = output_root / "southwark" / "southwark_licences.json"
    metadata_path = output_root / "southwark" / "metadata.json"

    assert dataset_path.exists()
    assert metadata_path.exists()

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    entry = data[0]
    assert entry["reference"] == "SWK-0001"
    assert entry["address"] == "10 Example Street, London SE1 0AA"
    assert entry["address"] != entry["detail_url"]

    assert len(records) == 1
    assert records[0].occupancy == 5

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata[0]["reference"] == "SWK-0001"
    assert metadata[0]["licence_type"] == "Mandatory licence"
