.PHONY: install test lint format typecheck scrape

install:
python -m venv .venv
. .venv/bin/activate && pip install -r requirements.txt && patchright install chromium

lint:
ruff check .

format:
ruff format .

typecheck:
mypy southwark

test:
pytest

scrape:
python -m southwark.runner
