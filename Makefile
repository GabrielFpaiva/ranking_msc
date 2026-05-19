VENV := .venv/bin
PYTHON := $(VENV)/python

.PHONY: bootstrap config dirs dev-backend dev-frontend lint typecheck test frontend-lint frontend-typecheck frontend-build validate ci

bootstrap:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	cd web && npm install
	$(MAKE) config
	$(MAKE) dirs

config:
	test -f config/settings.yaml || cp config/settings.yaml.example config/settings.yaml

dirs:
	mkdir -p data/snapshots data/reports data/logs

dev-backend:
	$(PYTHON) -m uvicorn app.api.main:app --reload --port 8000

dev-frontend:
	cd web && npm run dev

lint:
	$(PYTHON) -m ruff check src/ tests/ app/

typecheck:
	$(PYTHON) -m mypy src/ app/api/

test:
	$(PYTHON) -m pytest --cov=ranking_msc --cov-report=term-missing --cov-fail-under=80

frontend-lint:
	cd web && npm run lint

frontend-typecheck:
	cd web && npm run typecheck

frontend-build:
	cd web && npm run build

validate: lint typecheck test frontend-lint frontend-typecheck frontend-build

ci: validate
