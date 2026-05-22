#!/bin/sh
set -eu

if [ ! -f config/settings.yaml ]; then
  cp config/settings.yaml.example config/settings.yaml
fi

mkdir -p data/snapshots data/reports data/logs

exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
