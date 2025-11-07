# Repository Guidelines

## Project Structure
The scraper focuses solely on the Southwark council register.  Core code lives in the `southwark/` package which contains configuration, browser helpers, HTML parsing utilities, the runner, and the CLI.  Output artefacts are written to `data/southwark/` by default.  Test fixtures and regression tests sit under `tests/`.

## Development Commands
Create a virtual environment with `python -m venv .venv` and install dependencies via `pip install -r requirements.txt`.  Provision the Chromium binary once using `patchright install chromium`.  Run the scraper with `python -m southwark.runner`.  The regression suite is executed with `pytest`.  `ruff check` and `mypy southwark` provide linting and type coverage.

## Coding Style
Follow PEP 8: 4-space indentation, snake_case names, and clear docstrings for key functions.  Avoid unnecessary abstraction—the goal is a small, readable codebase.  Use `SnapshotMode` values (`none` or `all`) when adding CLI options that affect snapshotting.

## Testing
Tests live in `tests/` and should rely on the existing dry-run fixtures where possible.  New parsing behaviour should be accompanied by fixture-based tests to avoid hitting the live council site.
