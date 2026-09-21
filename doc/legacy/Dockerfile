FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY src ./src
COPY ref ./ref
COPY config/settings.yaml.example ./config/settings.yaml.example
# create_user.py é chamado pelo entrypoint no provisionamento via env vars.
COPY scripts/create_user.py ./scripts/create_user.py
# config_check.py precisa rodar ONDE a configuração vive. Em produção o
# settings.yaml chega por bind mount de ./config, e o host pode não ter venv:
# `docker exec ranking_msc_app python scripts/config_check.py` é o caminho.
COPY scripts/config_check.py ./scripts/config_check.py
COPY --from=frontend-builder /app/web/dist ./web/dist
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh     && pip install --upgrade pip     && pip install .
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
