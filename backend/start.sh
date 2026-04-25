#!/bin/sh
# Combined backend + Celery worker entrypoint for single-instance Render Web Service.
# - Celery worker runs in background (consumes the same Redis the API publishes to)
# - Uvicorn is the foreground PID 1 so Render reads its health checks correctly
#
# Memory tuning for Render free tier (~512 MB RAM):
#   MALLOC_ARENA_MAX=2           caps glibc malloc arenas — without this the
#                                worker's virtual RSS balloons to ~600 MB on
#                                multi-page OCR even though resident is small
#   --concurrency=1              one PDF at a time (multi-PDF bulk = sequential)
#   --prefetch-multiplier=1      worker grabs one task only, never queues extras
#   --max-tasks-per-child=20     recycle the worker every 20 tasks to release any
#                                memory leaked by tesseract / pdf2image
#   --max-memory-per-child=250000  recycle the worker when RSS hits ~250 MB,
#                                guaranteeing it never starves uvicorn (which
#                                needs ~150 MB to stay responsive on Render
#                                free tier 512 MB ceiling)
#   --without-gossip --without-mingle --without-heartbeat
#                                disables inter-worker chatter we don't need on
#                                a single-worker deployment, saving CPU + RAM
set -e

PORT="${PORT:-8001}"

# Bound glibc memory fragmentation for both uvicorn AND celery worker
export MALLOC_ARENA_MAX=2

# Background: Celery worker
celery -A celery_app.celery worker \
  --loglevel=info \
  --concurrency=1 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=20 \
  --max-memory-per-child=250000 \
  --without-gossip --without-mingle --without-heartbeat &

# Foreground: FastAPI / Uvicorn
exec uvicorn server:app --host 0.0.0.0 --port "${PORT}"
