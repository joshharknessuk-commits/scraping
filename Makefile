.PHONY: install test southwark-dry-run lambeth-dry-run

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m patchright install chromium

test:
	pytest

southwark-dry-run:
	python -m southwark.runner --dry-run --fixture-dir tests/fixtures/southwark --out-dir data/southwark

lambeth-dry-run:
	python -m lambeth.runner --dry-run --fixture-dir tests/fixtures/lambeth --out-dir data/lambeth
