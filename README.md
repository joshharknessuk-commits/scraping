# UK Council Licence Scraping

This repository contains modular scrapers for council HMO licence registers.  Both the Southwark and Lambeth scrapers share a
common core for browser automation, caching, and output handling.

```
scraping/
  common/         # shared browser, config, parsing, storage, orchestration
  southwark/      # Southwark specific configuration and CLI
  lambeth/        # Lambeth specific configuration and CLI
  data/           # scrape outputs (HTML, JSON, logs)
  tests/          # lightweight regression tests & fixtures
```

## Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
```

## Running the scrapers

Each scraper exposes both a CLI and a module entry point.  By default the scrapers read postcodes from the matching
`<council>_postcodes.txt` file in the repository root and write results beneath `data/<council>/`.

```bash
# Southwark
python -m southwark.runner --snapshot-mode all

# Lambeth
python -m lambeth.runner --concurrency 4 --jsonl-output
```

Key options available in both CLIs:

* `--postcodes-file` – path to a newline separated postcode list.
* `--out-dir` – override the output directory.
* `--snapshot-mode {none,all}` – control HTML snapshot persistence.
* `--jsonl-output` / `--no-json-array` – choose output formats.
* `--dry-run` – replay HTML fixtures instead of hitting the live site (defaults to `tests/fixtures/<council>`; override with `--mock-data-dir`).

## Dry-run fixtures & tests

A dry-run mode is provided for automated validation.  The settings factory accepts `dry_run=True` which replays HTML fixtures
from `tests/fixtures/<council>`.

```python
from southwark.config import Settings
from southwark.runner import run

records = run(["SE1 0AA"], Settings(dry_run=True))
print(len(records))
```

Run the full regression suite with pytest:

```bash
pytest
```

## Outputs

Each scraper writes:

* HTML search pages, licence detail pages, and additional info pages when snapshotting is enabled.
* `data/<council>/<council>_licences.json` – JSON array of all licences.
* `data/<council>/<council>_licences.jsonl` – streaming log of captures (optional).
* `data/<council>/metadata.json` – metadata for downstream processing.
* `data/<council>/logs/` – combined fetch logs and retry summaries.

Existing datasets and metadata are rehydrated automatically unless `--force` is supplied, enabling incremental scrapes.
