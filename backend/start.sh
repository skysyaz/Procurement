#!/bin/sh
# Combined backend + Celery worker entrypoint for single-instance Render Web Service.
# - Celery worker runs in background (consumes the same Redis the API publishes to)
# - Uvicorn is the foreground PID 1 so Render reads its health checks correctly
set -e

PORT="${PORT:-8001}"

# Background: Celery worker
celery -A celery_app.celery worker --loglevel=info --concurrency=2 &

# Foreground: FastAPI / Uvicorn
exec uvicorn server:app --host 0.0.0.0 --port "${PORT}"
