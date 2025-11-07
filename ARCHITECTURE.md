# Repository Architecture Overview

This document summarises the major refactor that reorganised the project into
shared infrastructure and council-specific packages.

## High-level layout

```
scraping/
  common/      # browser, orchestration, parsing, storage, shared models
  southwark/   # council-specific configuration, search, parser, CLI entry
  lambeth/     # council-specific configuration, search, parser, CLI entry
  data/        # scraping outputs and dry-run fixtures
  tests/       # pytest harness and HTML fixtures used for dry runs
```

Each scraper imports the shared helpers from `common/` and plugs in its own
parsing and search adapters.  The `common.runner` orchestrator coordinates the
postcode queue, retry handling, and filesystem writes while respecting
timeouts, throttling, and dry-run playback.

## Execution entry points

* `python -m southwark.runner` and `python -m lambeth.runner` execute live runs
  (or dry runs when passing the `--dry-run` flag).
* The CLI wrappers in `southwark/cli.py` and `lambeth/cli.py` surface user
  options for selecting postcodes, output destinations, and retry behaviour.
* `Makefile` targets provide shortcuts for installing dependencies, running
  tests, and launching dry-run scrapes.

## Testing strategy

The `tests/` directory contains pytest-based regression checks that run the
Southwark scraper in dry-run mode against deterministic HTML fixtures.  The
fixtures mirror council responses for search, additional listing, and detail
pages, allowing the pipeline to be validated without making live network
requests.

## Browser lifecycle

`common.browser.BrowserEnv` encapsulates the Patchright lifecycle with explicit
context management, retry helpers, throttling, and exponential backoff.  Shared
settings (`common.config.ScraperSettings`) control timeouts, headless mode,
retry counts, delay ranges, and output locations.

## Storage reliability

`common.storage` centralises filesystem writes with atomic JSON/JSONL helpers,
ensuring output directories are created with `os.makedirs(..., exist_ok=True)`
and writes occur through temporary files where appropriate.  The module also
exposes snapshot utilities for raw HTML archiving.

## Parser abstractions

Common parsing utilities (`common.parsing`) expose reusable helpers for
navigating council HTML, with council-specific modules defining selector maps
and attribute extraction.  Parsed results use shared dataclasses from
`common.models` to keep the schema aligned across councils.
