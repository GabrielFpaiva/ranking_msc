VENV := .venv/bin

.PHONY: lint typecheck test ci

lint:
	$(VENV)/ruff check src/ tests/

typecheck:
	$(VENV)/mypy src/

test:
	$(VENV)/pytest --cov=ranking_msc --cov-report=term-missing --cov-fail-under=80

ci: lint typecheck test
