.PHONY: all install dev test lint clean format

UV  := uv
PYTHON := $(UV) run python

all: install

install:
	$(UV) sync

dev:
	$(UV) sync --dev

test:
	$(UV) run pytest -v --tb=short

lint:
	$(UV) run ruff check src/h265ify/
	$(UV) run ruff format --check src/h265ify/

format:
	$(UV) run ruff check --fix src/h265ify/
	$(UV) run ruff format src/h265ify/

clean:
	rm -rf .venv/
	rm -rf __pycache__ src/*/__pycache__ tests/__pycache__
	rm -rf *.egg-info src/*.egg-info
	rm -rf .pytest_cache .ruff_cache
	rm -rf dist/ build/
	find . -name '*.pyc' -delete

.env:
	cp .env.sample .env
