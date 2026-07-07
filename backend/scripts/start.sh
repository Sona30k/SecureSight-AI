#!/bin/sh
set -eu
alembic upgrade head
if [ "${DEMO_MODE:-false}" = "true" ]; then
  python -m scripts.seed
fi
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
  --timeout-keep-alive "${KEEP_ALIVE_SECONDS:-10}" \
  --log-level "${LOG_LEVEL:-info}"
