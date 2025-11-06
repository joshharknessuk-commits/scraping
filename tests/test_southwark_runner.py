import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.config import SnapshotMode
from southwark.config import Settings
from southwark.runner import run


def test_southwark_dry_run(tmp_path):
    output_root = tmp_path / "southwark"
    settings = Settings(
        output_root=output_root,
        dry_run=True,
        fixture_dir=Path("tests/fixtures/southwark"),
        json_array_output=True,
        jsonl_output=False,
        snapshot_mode=SnapshotMode.NONE,
    )

    records = run(["SE1 0AA"], settings)
    assert records
    assert records[0].reference == "SWK-1234"
    assert records[0].address == "1 Example Street, London SE1 0AA"

    json_path = output_root / "southwark_licences.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload[0]["reference"] == "SWK-1234"
    assert payload[0]["address"].startswith("1 Example Street")

    metadata_path = output_root / "metadata.json"
    assert metadata_path.exists()
