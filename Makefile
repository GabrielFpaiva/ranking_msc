VENV := .venv/bin
PYTHON := $(VENV)/python

.PHONY: bootstrap config dirs dev-backend dev-frontend lint typecheck test frontend-lint frontend-typecheck frontend-build validate ci docker-up docker-down gen-cert prod-up prod-down

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


docker-up:
	docker compose up --build

docker-down:
	docker compose down

CERT_DIR := docker/nginx/certs
CERT_CN ?= localhost

gen-cert:
	@if [ -f $(CERT_DIR)/fullchain.pem ]; then \
		echo "Certificado já existe em $(CERT_DIR)/ — não sobrescrevendo."; \
	else \
		mkdir -p $(CERT_DIR); \
		CERT_TMP_CNF=$$(mktemp); \
		printf '%s\n' \
			'[req]' \
			'distinguished_name = dn' \
			'x509_extensions = v3_req' \
			'prompt = no' \
			'[dn]' \
			'CN = $(CERT_CN)' \
			'[v3_req]' \
			'subjectAltName = DNS:$(CERT_CN),DNS:localhost,IP:127.0.0.1' \
			> $$CERT_TMP_CNF; \
		openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
			-keyout $(CERT_DIR)/privkey.pem \
			-out $(CERT_DIR)/fullchain.pem \
			-config $$CERT_TMP_CNF -extensions v3_req; \
		rm -f $$CERT_TMP_CNF; \
		echo "Certificado self-signed gerado em $(CERT_DIR)/ (CN=$(CERT_CN))."; \
	fi

prod-up:
	docker compose -f docker-compose.prod.yml up --build -d

prod-down:
	docker compose -f docker-compose.prod.yml down
