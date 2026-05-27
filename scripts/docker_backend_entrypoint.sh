#!/bin/sh
set -eu

mkdir -p /app/data /app/exports /app/backups

python scripts/init_local_db.py

exec uvicorn app.api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}" --proxy-headers
