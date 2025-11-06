.PHONY: install test lint format scrape-southwark scrape-lambeth

install:
python -m venv .venv
. .venv/bin/activate && pip install -r requirements.txt && patchright install chromium

lint:
ruff check .

format:
ruff format .

mypy:
mypy common southwark lambeth

test:
pytest

scrape-southwark:
python -m southwark.runner

scrape-lambeth:
python -m lambeth.runner
