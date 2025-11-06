# Repository Guidelines

## Project Structure & Module Organization
Core scraping logic lives in `southwark_scraper/`, which bundles the Playwright browser helpers, parsing utilities, and storage helpers. CLI entry points `southwark_fetch.py` (acquire HTML) and `southwark_parse.py` (offline parse) sit in the repository root. Generated artefacts are written to `data/southwark/`, including search-page snapshots, licence detail HTML, logs, and the JSON/CSV datasets. Reference inputs such as `southwark_postcodes.txt` also live at the root. If you add automated tests, mirror the package layout under `tests/`.

## Build, Test, and Development Commands
`python3 -m venv .venv && source .venv/bin/activate` creates and activates the project virtual environment. `pip install -r requirements.txt` installs runtime and tooling dependencies. Run `playwright install chromium` once per machine to provision the browser binary. Use `python3 southwark_fetch.py` for a full headless scrape, or add flags such as `--headed`, `--max-pages 1`, or `--force` for debugging. Execute `python3 southwark_parse.py` to regenerate structured outputs from cached HTML. `python3 -m compileall southwark_scraper` offers a quick syntax check.

## Coding Style & Naming Conventions
Follow PEP 8 conventions: 4-space indentation, snake_case functions, PascalCase classes, and module-level constants in UPPER_SNAKE_CASE. Keep imports explicit and sorted logically. Logging should use the existing namespaces (`southwark.scraper`, `southwark.parse`) and favour actionable messages. Before submitting, run `ruff check` for linting and `mypy southwark_scraper` for type validation.

## Testing Guidelines
Adopt `pytest` for new tests. Name files `test_<module>.py` and place them under `tests/`, mirroring the source hierarchy. Prefer fixtures for Playwright setup/teardown and include representative HTML fixtures when asserting parser behaviour. Ensure new features include at least one regression test verifying expected output records.

## Commit & Pull Request Guidelines
Write commit subjects in the imperative mood (e.g., `Add Southwark pagination guard`) with additional context in the body when needed. Squash incidental commits before publishing a review. PR descriptions must summarise the change, list validation commands, and mention data backfills or manual steps. Include screenshots or log snippets for any user-visible scraper behaviour change.

## Security & Configuration Tips
Do not commit credentials; the scraper targets public pages and should remain keyless. Respect council rate limits—retain the default delay range unless you have explicit approval to alter it. Keep personal data sourced from the register within the generated artefacts directory and share responsibly.
