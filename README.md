# Southwark Licence Scraper

This repository contains a single scraper that captures Houses in Multiple Occupation (HMO) and selective licence records from the London Borough of Southwark.  The scraper uses Patchright (Playwright) to drive the dynamic search form and BeautifulSoup to parse each licence page.  Results are written both as a JSON array and as a newline-delimited JSONL stream so downstream tooling can process licences incrementally.

```
scraping/
  southwark/        # scraper code and CLI
  data/             # JSON/JSONL outputs and optional HTML snapshots
  tests/            # dry-run fixtures and regression tests
  requirements.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
```

## Running a scrape

The CLI expects a newline-delimited list of postcodes.  By default it reads `southwark_postcodes.txt` in the repository root and writes to `data/southwark/`.

```bash
python -m southwark.runner --postcodes-file southwark_postcodes.txt --snapshot-mode all
```

Common flags:

* `--out-dir`: change the output directory.
* `--headed`: launch Chromium with a visible window.
* `--max-pages`: stop after the given number of search result pages per postcode.
* `--retries` / `--retry-backoff`: tune retry behaviour when Southwark throttles requests.
* `--snapshot-mode {none,all}`: write HTML snapshots for search/detail/additional pages.
* `--no-jsonl` / `--no-json`: toggle JSONL or aggregated JSON outputs.
* `--dry-run`: replay HTML fixtures from `tests/fixtures/southwark`.

Programmatic use mirrors the CLI:

```python
from southwark import SouthwarkSettings, run

settings = SouthwarkSettings(dry_run=True, snapshot_mode="all")
records = run(["SE1 0AA"], settings)
print(len(records))
```

## Outputs

Every run writes the following files beneath the chosen output directory:

* `southwark_licences.json`: array of licence records with reference, address, expiry, licence type, occupancy, and detail URL.
* `southwark_licences.jsonl`: streaming log (one JSON object per line) for incremental ingestion.
* `metadata.json`: capture metadata containing postcodes, timestamps, and source URLs.
* Optional HTML snapshots in `search_pages/`, `licence_pages/`, and `additional_pages/` when `--snapshot-mode all` is enabled.

## Tests and dry runs

Fixtures under `tests/fixtures/southwark/` emulate a single postcode search so the scraper can be validated without making live requests.  Run the regression test suite with:

```bash
pytest
```

The test suite executes a dry-run scrape and asserts that JSON, JSONL, metadata, and snapshot outputs are produced correctly.
