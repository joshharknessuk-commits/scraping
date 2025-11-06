# UK Council HMO Scraping

This repository collects public HMO licence records for Southwark and Lambeth councils using Patchright (Playwright) automation. The codebase now shares a common orchestration layer and storage helpers so each council module only maintains its parsing rules and configuration.

## Repository layout

```
common/           # shared browser, config, storage, orchestration helpers
southwark/        # Southwark specific config, parsing and CLI entry
lambeth/          # Lambeth specific config, parsing and CLI entry
tests/            # pytest-based smoke tests with HTML fixtures
data/             # default output location for scraped artefacts
requirements.txt  # Python runtime and tooling dependencies
```

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m patchright install chromium
```

> The Playwright browser download only needs to run once per machine.

## Running the scrapers

Both scrapers expose a CLI so you can run them directly with `python -m`:

```bash
# Southwark scrape
python -m southwark.runner --postcodes-file southwark_postcodes.txt

# Lambeth scrape
python -m lambeth.runner --postcodes-file lambeth_postcodes.txt
```

Important flags:

- `--headed` launches Chromium with a visible window for debugging.
- `--force` ignores cached HTML snapshots and refetches everything.
- `--jsonl-output` streams captured licences to a JSONL file while the scrape runs.
- `--dry-run --fixture-dir tests/fixtures/<council>` replays the static HTML used by the automated tests.

Outputs default to `data/<council>/` and include search snapshots, licence HTML, metadata and `*_licences.json`.

## Dry-run fixture mode

For development or CI testing you can disable live browsing entirely:

```bash
python -m southwark.runner --dry-run --fixture-dir tests/fixtures/southwark --out-dir data/southwark
```

The runner parses the bundled HTML fixtures, writes the dataset and metadata files, and exits without launching Patchright.

## Tests

Lightweight regression tests validate the dry-run flow for both councils:

```bash
pytest
```

Each test executes one postcode scrape using the fixture HTML, asserts the resulting JSON payload, and verifies the output files are created correctly.

## Coding standards

- Code follows PEP 8 with type hints across modules.
- All writes use safe directory creation to avoid permission errors.
- Logging reports start/end status, retry attempts, and failure summaries per run.

Refer to `AGENTS.md` for additional contribution guidelines.
