#!/bin/sh
set -eu

if [ ! -f config/settings.yaml ]; then
  cp config/settings.yaml.example config/settings.yaml
fi

# Provisionamento sem passo manual: com as env vars definidas, cria/atualiza
# o usuário admin (hash bcrypt + secret_key seguro gerados automaticamente).
#
# RANKING_MSC_SECRET_KEY é opcional mas recomendado em hosts sem disco
# persistente (ex.: Render free): sem ela, todo restart do container recria
# settings.yaml do zero e gera um secret_key novo, invalidando na hora todo
# JWT emitido antes — os usuários caem pro /login a cada reinício.
if [ -n "${RANKING_MSC_ADMIN_USERNAME:-}" ] && [ -n "${RANKING_MSC_ADMIN_PASSWORD:-}" ]; then
  set -- python scripts/create_user.py \
    --username "${RANKING_MSC_ADMIN_USERNAME}" \
    --password-env RANKING_MSC_ADMIN_PASSWORD
  if [ -n "${RANKING_MSC_SECRET_KEY:-}" ]; then
    set -- "$@" --secret-key-env RANKING_MSC_SECRET_KEY
  fi
  "$@"
fi

mkdir -p data/snapshots data/reports data/logs data/uso

exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
