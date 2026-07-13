#!/bin/sh
set -eu

if [ ! -f config/settings.yaml ]; then
  cp config/settings.yaml.example config/settings.yaml
fi

# Provisionamento sem passo manual: com as env vars definidas, cria/atualiza
# o usuário admin (hash bcrypt + secret_key seguro gerados automaticamente).
if [ -n "${RANKING_MSC_ADMIN_USERNAME:-}" ] && [ -n "${RANKING_MSC_ADMIN_PASSWORD:-}" ]; then
  python scripts/create_user.py \
    --username "${RANKING_MSC_ADMIN_USERNAME}" \
    --password-env RANKING_MSC_ADMIN_PASSWORD
fi

mkdir -p data/snapshots data/reports data/logs

exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
