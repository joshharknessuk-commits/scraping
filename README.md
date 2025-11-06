# Council HMO scraping toolkit

This repository bundles Playwright-based scrapers for the Southwark and Lambeth HMO public registers. Each scraper shares a common
set of browser utilities, storage helpers, and orchestration logic to keep behaviour consistent across councils.

## Repository layout

```
common/           # shared browser, config, logging and persistence utilities
southwark/        # Southwark-specific config, fetch, parse, runner and fixtures
lambeth/          # Lambeth-specific modules mirroring the Southwark package
tests/            # pytest suite with dry-run fixtures
data/             # default output directory (JSON, HTML snapshots, logs)
requirements.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Running the scrapers

Both council packages expose a CLI entry point via `python -m`:

```bash
# Southwark
python -m southwark --dry-run --output-root data

# Lambeth
python -m lambeth --dry-run --output-root data
```

- Omit `--dry-run` to perform a live scrape with Patchright/Playwright.
- Provide explicit postcodes as positional arguments; otherwise the bundled postcode list is used.
- Outputs are written to `<output-root>/<council_slug>/` and include JSON datasets, metadata, HTML snapshots (when
  `SnapshotMode.ALL` is configured), and logs.
- Dry-run mode ships with a single demonstration postcode fixture per council. Any unspecified postcode is skipped with a log
  warning so you can target the bundled examples explicitly (`SE1 0AA` for Southwark, `SW9 0AA` for Lambeth).

Programmatic execution mirrors the CLI. The runner returns a list of `LicenceRecord` instances:

```python
from southwark import Settings, run

records = run(["SE1 0AA"], Settings(dry_run=True))
print(records[0].address)
```

## Tests and dry-run fixtures

The pytest suite exercises both scrapers using local HTML fixtures. To run the tests:

```bash
pytest
```

Dry-run mode reads HTML from `southwark/fixtures/` and `lambeth/fixtures/`, allowing the parsers to be validated without
live network traffic. The tests assert that JSON datasets, metadata files, and occupancy parsing behave as expected.

## Output artefacts

Every scrape writes the following artefacts under the council-specific output directory:

- `search_pages/`: optional search result snapshots when `SnapshotMode.ALL` is enabled.
- `licence_pages/` and `additional_pages/`: licence detail and supporting HTML.
- `metadata.json`: metadata for each captured licence, including URLs and occupancy counts.
- `<council>_licences.json` / `.jsonl`: structured datasets suitable for downstream analysis.
- `logs/`: rotating scraper logs and a `fetch_failures.log` when errors occur.

Dry-run invocations still emit these artefacts, making it easy to confirm integrations and expected schema changes.
