import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.config import SnapshotMode
from lambeth.config import Settings
from lambeth.runner import run


def test_lambeth_dry_run(tmp_path):
    output_root = tmp_path / "lambeth"
    settings = Settings(
        output_root=output_root,
        dry_run=True,
        fixture_dir=Path("tests/fixtures/lambeth"),
        json_array_output=True,
        jsonl_output=False,
        snapshot_mode=SnapshotMode.NONE,
    )

    records = run(["SW9 9ZZ"], settings)
    assert records
    assert records[0].reference == "LAM-0001"
    assert records[0].address == "10 Lambeth Walk, London SW9 9ZZ"

    json_path = output_root / "lambeth_licences.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload[0]["reference"] == "LAM-0001"
    assert payload[0]["occupancy"] == 3
