.PHONY: help install dev test lint format build deb clean

PYTHON ?= python3

help:
	@echo "make dev      - install in editable mode with dev extras"
	@echo "make test     - run the test suite"
	@echo "make lint     - run ruff"
	@echo "make format   - format with ruff"
	@echo "make build    - build the wheel and sdist"
	@echo "make deb      - build a .deb package"
	@echo "make clean    - remove build artefacts"

install:
	$(PYTHON) -m pip install .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

build:
	$(PYTHON) -m build

deb:
	sh packaging/build-deb.sh

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
