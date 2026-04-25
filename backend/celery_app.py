"""Celery application wrapped around Redis.

Runs the OCR→classify→extract pipeline asynchronously so bulk uploads scale
past the FastAPI BackgroundTasks limit. Falls back to in-process execution if
the worker is unreachable (see server.py `use_celery`).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_BACKEND_URL = os.environ.get("CELERY_BACKEND_URL", "redis://127.0.0.1:6379/1")

celery = Celery("procureflow", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)
celery.conf.task_acks_late = True
celery.conf.worker_prefetch_multiplier = 2
celery.conf.task_default_queue = "procureflow"

logger = logging.getLogger("procureflow.celery")


@celery.task(name="procureflow.process_document", bind=True, max_retries=2, default_retry_delay=5)
def process_document_task(self, doc_id: str) -> str:  # noqa: ARG001
    """Celery wrapper that runs the async pipeline synchronously inside a worker."""
    from services.classification_service import classify
    from services.extraction_service import extract_structured
    from services.ocr_service import extract_text_from_pdf
    from services import storage_service

    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ["DB_NAME"]]

    tmp_dir = ROOT_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    async def _run():
        from datetime import datetime, timezone

        # Worker may be a *separate* container from the API — never assume the
        # PDF is on local disk. Pull from R2 (with local-disk fallback for dev).
        located = await storage_service.ensure_local_copy(doc_id, tmp_dir)
        if located is None:
            await db.documents.update_one({"id": doc_id}, {"$set": {"status": "FAILED"}})
            return "missing-file"
        file_path, is_temp = located
        try:
            await db.documents.update_one({"id": doc_id}, {"$set": {"status": "PROCESSING"}})
            raw_text, ocr_method = extract_text_from_pdf(file_path)
            doc_type, confidence, method = await classify(raw_text)
            extracted = await extract_structured(doc_type, raw_text)
            await db.documents.update_one(
                {"id": doc_id},
                {"$set": {
                    "raw_text": raw_text,
                    "type": doc_type,
                    "confidence_score": confidence,
                    "classification_method": method,
                    "ocr_method": ocr_method,
                    "extracted_data": extracted,
                    "status": "EXTRACTED",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            return "ok"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Celery pipeline failed for %s: %s", doc_id, exc)
            await db.documents.update_one({"id": doc_id}, {"$set": {"status": "FAILED"}})
            raise
        finally:
            if storage_service.R2_CONFIGURED and file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass

    try:
        return asyncio.run(_run())
    finally:
        client.close()
