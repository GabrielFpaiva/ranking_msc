VENV := .venv/bin
PYTHON := $(VENV)/python

.PHONY: lint typecheck test frontend-lint frontend-build ci

lint:
	$(PYTHON) -m ruff check src/ tests/ app/

typecheck:
	$(PYTHON) -m mypy src/ app/api/

test:
	$(PYTHON) -m pytest --cov=ranking_msc --cov-report=term-missing --cov-fail-under=80

frontend-lint:
	cd web && npm run lint

frontend-build:
	cd web && npm run build

ci: lint typecheck test frontend-lint frontend-build
