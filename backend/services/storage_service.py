"""Object storage abstraction.

Primary backend: Cloudflare R2 (S3-compatible) — files persist across redeploys.
Fallback   : local disk at ``backend/uploads/`` (dev only; ephemeral on Render).

Configuration (all optional; missing/empty disables R2 and falls back to local):

    R2_BUCKET_NAME        e.g. procureflow-pdfs
    R2_ENDPOINT_URL       e.g. https://<account-id>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_KEY_PREFIX         optional, defaults to "documents"

All public functions are async-safe — sync boto3 calls are dispatched to a
thread pool so the FastAPI event loop is never blocked.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("procureflow.storage")

# ---------------------------------------------------------------------------
# Config (read once at import time)
# ---------------------------------------------------------------------------

_BUCKET = os.environ.get("R2_BUCKET_NAME", "").strip()
_ENDPOINT = os.environ.get("R2_ENDPOINT_URL", "").strip()
_AKID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
_SK = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
_PREFIX = os.environ.get("R2_KEY_PREFIX", "documents").strip().strip("/")

_LOCAL_FALLBACK = Path(__file__).resolve().parent.parent / "uploads"
_LOCAL_FALLBACK.mkdir(exist_ok=True)

R2_CONFIGURED: bool = bool(_BUCKET and _ENDPOINT and _AKID and _SK)
_CLIENT = None  # cached boto3 client; built lazily


def _client():
    """Lazy-init a boto3 S3 client pointed at R2. Returns None if unconfigured."""
    global _CLIENT
    if not R2_CONFIGURED:
        return None
    if _CLIENT is not None:
        return _CLIENT
    import boto3  # local import keeps server boot fast when R2 disabled
    from botocore.config import Config

    _CLIENT = boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_AKID,
        aws_secret_access_key=_SK,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )
    return _CLIENT


def _key(doc_id: str) -> str:
    return f"{_PREFIX}/{doc_id}.pdf" if _PREFIX else f"{doc_id}.pdf"


def _local_path(doc_id: str) -> Path:
    return _LOCAL_FALLBACK / f"{doc_id}.pdf"


def backend_name() -> str:
    return "r2" if R2_CONFIGURED else "local"


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def put_pdf_from_path(doc_id: str, src_path: Path) -> str:
    """Upload a local file to R2. No-op when R2 is unconfigured (file is the
    storage in that case). Returns the storage key/path used."""
    if not R2_CONFIGURED:
        return str(src_path)
    cl = _client()
    key = _key(doc_id)

    def _do() -> None:
        with open(src_path, "rb") as fh:
            cl.upload_fileobj(
                fh, _BUCKET, key,
                ExtraArgs={"ContentType": "application/pdf"},
            )

    await asyncio.to_thread(_do)
    logger.info("Uploaded %s to R2 (%s)", doc_id, key)
    return key


async def download_pdf(doc_id: str, dest: Path) -> Optional[Path]:
    """Download a PDF into ``dest``. Returns the destination path on success,
    or None if the object is missing / cannot be fetched."""
    if not R2_CONFIGURED:
        src = _local_path(doc_id)
        return src if src.exists() else None
    cl = _client()
    key = _key(doc_id)

    def _do() -> None:
        cl.download_file(_BUCKET, key, str(dest))

    try:
        await asyncio.to_thread(_do)
        return dest
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 download failed for %s (%s): %s", doc_id, key, exc)
        return None


async def delete_pdf(doc_id: str) -> None:
    """Best-effort delete from both local disk and R2."""
    local = _local_path(doc_id)
    if local.exists():
        try:
            local.unlink()
        except OSError:
            pass
    if not R2_CONFIGURED:
        return
    cl = _client()
    try:
        await asyncio.to_thread(cl.delete_object, Bucket=_BUCKET, Key=_key(doc_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 delete failed for %s: %s", doc_id, exc)


async def presigned_get_url(
    doc_id: str,
    *,
    filename: Optional[str] = None,
    expires: int = 600,
) -> Optional[str]:
    """Return a short-lived presigned GET URL the browser can fetch directly.
    Returns None when R2 is unconfigured or the call fails."""
    if not R2_CONFIGURED:
        return None
    cl = _client()
    params: dict = {"Bucket": _BUCKET, "Key": _key(doc_id)}
    if filename:
        # Sanitize: drop CR/LF, keep simple ASCII; quoting handled by boto.
        safe = "".join(ch for ch in filename if ch.isprintable() and ch not in "\r\n\"")
        params["ResponseContentDisposition"] = f'inline; filename="{safe}"'
    params["ResponseContentType"] = "application/pdf"
    try:
        return await asyncio.to_thread(
            cl.generate_presigned_url, "get_object",
            Params=params, ExpiresIn=int(expires),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 presign failed for %s: %s", doc_id, exc)
        return None


async def exists(doc_id: str) -> bool:
    """True if the object is reachable in R2 (or present on local disk)."""
    if not R2_CONFIGURED:
        return _local_path(doc_id).exists()
    cl = _client()
    try:
        await asyncio.to_thread(cl.head_object, Bucket=_BUCKET, Key=_key(doc_id))
        return True
    except Exception:  # noqa: BLE001
        return False


async def ensure_local_copy(doc_id: str, dest_dir: Path) -> Optional[tuple[Path, bool]]:
    """Make sure a local copy of the PDF exists for OCR / processing.

    Returns (path, is_temporary).  ``is_temporary`` indicates the caller should
    delete the file when finished.  Returns None when the PDF cannot be located.
    """
    persistent = _local_path(doc_id)
    if persistent.exists():
        return persistent, False
    if not R2_CONFIGURED:
        return None
    dest_dir.mkdir(exist_ok=True)
    tmp = dest_dir / f"{doc_id}.pdf"
    fetched = await download_pdf(doc_id, tmp)
    if fetched is None:
        return None
    return fetched, True
