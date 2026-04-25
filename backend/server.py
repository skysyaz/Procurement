from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import (
    APIRouter, BackgroundTasks, Depends, FastAPI, File, HTTPException,
    Query, Request, Response, UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, Response as FastResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

from services.audit_service import AuditEvent, log_from_user, write_log
from services.auth_service import (
    ROLES, clear_auth_cookies, create_access_token, create_refresh_token,
    decode, hash_password, make_auth_deps, new_user_doc, public_user,
    set_auth_cookies, verify_password,
)
from services.classification_service import classify
from services.email_service import (
    is_configured as email_configured,
    send_password_reset_email,
    send_pdf_email,
)
from services.extraction_service import extract_structured
from services.ocr_service import extract_text_from_pdf
from services.pdf_service import render_document_pdf
from services.templates import (
    DEFAULT_TEMPLATES, get_template, is_builtin, list_templates,
    remove_runtime_template, set_runtime_templates, upsert_runtime_template,
    validate_schema,
)


UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="ProcureFlow API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("procureflow")

auth_deps = make_auth_deps(db)
get_current_user = auth_deps["get_current_user"]
require_min_role = auth_deps["require_min_role"]
require_roles = auth_deps["require_roles"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOC_STATUSES = ["UPLOADED", "PROCESSING", "EXTRACTED", "REVIEWED", "FINAL", "MANUAL_DRAFT", "FAILED"]
DOC_TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"]
DOC_SOURCES = ["AUTO", "MANUAL"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "OTHER"
    status: str = "UPLOADED"
    source: str = "AUTO"
    filename: Optional[str] = None
    file_url: Optional[str] = None
    raw_text: Optional[str] = ""
    confidence_score: float = 0.0
    classification_method: Optional[str] = None
    ocr_method: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    owner_id: Optional[str] = None
    owner_email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewPayload(BaseModel):
    extracted_data: Dict[str, Any]
    status: Optional[str] = None
    type: Optional[str] = None


class CreateDocumentPayload(BaseModel):
    type: str
    data: Dict[str, Any]


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class EmailPayload(BaseModel):
    to: EmailStr
    cc: Optional[EmailStr] = None
    subject: Optional[str] = None
    message: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role: str


class ForgotPasswordPayload(BaseModel):
    email: EmailStr


class ResetPasswordPayload(BaseModel):
    token: str
    password: str = Field(min_length=8)


class TemplatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_type: str
    label: str
    template_schema: Dict[str, Any] = Field(alias="schema")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    for k in ("created_at", "updated_at"):
        v = doc.get(k)
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@api_router.post("/auth/register")
async def register(payload: RegisterPayload, response: Response, request: Request):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # First ever user becomes admin; otherwise default to `user`
    count = await db.users.count_documents({})
    role = "admin" if count == 0 else "user"
    doc = new_user_doc(email=email, password=payload.password, name=payload.name, role=role)
    await db.users.insert_one(doc)

    access = create_access_token(doc["id"], doc["email"], doc["role"])
    refresh = create_refresh_token(doc["id"])
    set_auth_cookies(response, access, refresh)

    await log_from_user(
        db, doc,
        action="USER_REGISTER", target_type="user", target_id=doc["id"],
    )
    return {"user": public_user(doc), "access_token": access}


async def _check_lockout(identifier: str) -> None:
    rec = await db.login_attempts.find_one({"identifier": identifier})
    locked_until = (rec or {}).get("locked_until")
    if isinstance(locked_until, str):
        locked_until = datetime.fromisoformat(locked_until)
    if locked_until and locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")


async def _record_failure(identifier: str, client_ip: str) -> None:
    from datetime import timedelta
    rec = await db.login_attempts.find_one({"identifier": identifier}) or {}
    attempts = rec.get("count", 0) + 1
    update: Dict[str, Any] = {
        "count": attempts, "identifier": identifier, "last_ip": client_ip,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if attempts >= 5:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)


@api_router.post("/auth/login")
async def login(payload: LoginPayload, response: Response, request: Request):
    email = payload.email.lower().strip()
    # Key solely on email so lockout survives multi-pod ingress.
    identifier = email
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = fwd or (request.client.host if request.client else "unknown")

    await _check_lockout(identifier)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await _record_failure(identifier, client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": identifier})

    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)

    await log_from_user(
        db, user,
        action="USER_LOGIN", target_type="user", target_id=user["id"],
    )
    return {"user": public_user(user), "access_token": access}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    # Always clear cookies — do NOT gate this on token validity.
    # If the token is expired, Depends(get_current_user) would return 401,
    # clear_auth_cookies would never run, and the browser would keep the cookies.
    clear_auth_cookies(response)
    # Best-effort audit log: only possible when the access token is still valid.
    try:
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if token:
            payload = decode(token)
            if payload.get("type") == "access":
                user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
                if user:
                    await log_from_user(
                        db, user,
                        action="USER_LOGOUT", target_type="user", target_id=user["id"],
                    )
    except Exception:  # noqa: BLE001
        pass  # expired / invalid token — cookies are still cleared above
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@api_router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(user["id"], user["email"], user["role"])
        new_refresh = create_refresh_token(user["id"])
        set_auth_cookies(response, access, new_refresh)
        return {"access_token": access}
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

@api_router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    """Always returns 200 so attackers can't enumerate emails."""
    import secrets
    from datetime import timedelta

    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["id"],
            "email": email,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
        reset_url = f"{frontend_url}/reset-password?token={token}"
        if email_configured():
            try:
                send_password_reset_email(email, reset_url)
                logger.info("Sent password reset to %s", email)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send reset email: %s", exc)
        else:
            logger.warning("RESEND_API_KEY missing — reset link for %s: %s", email, reset_url)

        await log_from_user(
            db, user,
            action="PASSWORD_RESET_REQUESTED", target_type="user", target_id=user["id"],
            meta={"email_sent": email_configured()},
        )
    return {"ok": True}


@api_router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    rec = await db.password_reset_tokens.find_one({"token": payload.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or already-used token")
    expires_at = rec.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")

    await db.users.update_one(
        {"id": rec["user_id"]},
        {"$set": {"password_hash": hash_password(payload.password),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.password_reset_tokens.update_one(
        {"token": payload.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.login_attempts.delete_one({"identifier": rec["email"]})
    await write_log(db, AuditEvent(
        actor_id=rec["user_id"], actor_email=rec["email"],
        action="PASSWORD_RESET_COMPLETED", target_type="user", target_id=rec["user_id"],
    ))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin: user management + audit log
# ---------------------------------------------------------------------------

@api_router.get("/admin/users")
async def list_users(_: dict = Depends(require_roles("admin"))):
    cursor = db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1)
    return [u async for u in cursor]


@api_router.put("/admin/users/{user_id}/role")
async def change_user_role(user_id: str, payload: UserRoleUpdate, actor: dict = Depends(require_roles("admin"))):
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {ROLES}")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["id"] == actor["id"] and payload.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": payload.role, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await log_from_user(
        db, actor,
        action="USER_ROLE_CHANGE", target_type="user", target_id=user_id,
        meta={"new_role": payload.role, "old_role": target["role"]},
    )
    return {"ok": True}


@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, actor: dict = Depends(require_roles("admin"))):
    if user_id == actor["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.delete_one({"id": user_id})
    await log_from_user(
        db, actor,
        action="USER_DELETE", target_type="user", target_id=user_id, meta={"email": target["email"]},
    )
    return {"ok": True}


@api_router.get("/audit-logs")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    _: dict = Depends(require_roles("admin")),
):
    q: Dict[str, Any] = {}
    if action:
        q["action"] = action
    if actor_email:
        q["actor_email"] = actor_email.lower().strip()
    cursor = db.audit_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return [log async for log in cursor]


# ---------------------------------------------------------------------------
# Admin: template editor
# ---------------------------------------------------------------------------

async def _refresh_templates_from_db() -> None:
    cursor = db.document_templates.find({}, {"_id": 0})
    overrides = {doc["document_type"]: doc async for doc in cursor}
    set_runtime_templates(overrides)


@api_router.post("/admin/templates")
async def create_template(payload: TemplatePayload, actor: dict = Depends(require_roles("admin"))):
    # Reject lowercase/invalid raw input (don't silently upshift) so admins
    # see immediate validation feedback instead of being surprised later.
    raw_type = payload.document_type.strip()
    if not re.fullmatch(r"[A-Z0-9_]{2,32}", raw_type):
        raise HTTPException(
            status_code=400,
            detail="document_type must be 2-32 chars, uppercase letters, digits or underscores only",
        )
    dtype = raw_type
    err = validate_schema(payload.template_schema)
    if err:
        raise HTTPException(status_code=400, detail=err)

    tpl = {"document_type": dtype, "label": payload.label.strip() or dtype, "schema": payload.template_schema}
    await db.document_templates.update_one({"document_type": dtype}, {"$set": tpl}, upsert=True)
    upsert_runtime_template(tpl)

    await log_from_user(
        db, actor,
                    action="TEMPLATE_UPSERT", target_type="template", target_id=dtype,
                    meta={"label": tpl["label"]})
    return tpl


@api_router.put("/admin/templates/{doc_type}")
async def update_template(doc_type: str, payload: TemplatePayload, actor: dict = Depends(require_roles("admin"))):
    if payload.document_type.upper() != doc_type.upper():
        raise HTTPException(status_code=400, detail="document_type in body must match URL")
    return await create_template(payload, actor)


@api_router.delete("/admin/templates/{doc_type}")
async def delete_template(doc_type: str, actor: dict = Depends(require_roles("admin"))):
    dtype = doc_type.upper()
    if is_builtin(dtype):
        # Built-ins can't be removed — only reset: delete the override to fall back.
        result = await db.document_templates.delete_one({"document_type": dtype})
        remove_runtime_template(dtype)
        # Put the factory default back on disk so list endpoint shows it unchanged
        await log_from_user(
        db, actor,
                        action="TEMPLATE_RESET", target_type="template", target_id=dtype)
        return {"reset": True, "found_override": result.deleted_count > 0}

    result = await db.document_templates.delete_one({"document_type": dtype})
    remove_runtime_template(dtype)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    await log_from_user(
        db, actor,
                    action="TEMPLATE_DELETE", target_type="template", target_id=dtype)
    return {"deleted": dtype}


# ---------------------------------------------------------------------------
# Public(ish) routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "ProcureFlow API", "version": "1.1", "email_configured": email_configured()}


@api_router.get("/templates")
async def get_templates():
    return {"templates": list_templates()}


@api_router.get("/templates/{doc_type}")
async def get_one_template(doc_type: str):
    tpl = get_template(doc_type)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    scope: Dict[str, Any] = {} if user["role"] in {"admin", "manager"} else {"owner_id": user["id"]}
    total = await db.documents.count_documents(scope)
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for t in DOC_TYPES:
        by_type[t] = await db.documents.count_documents({**scope, "type": t})
    for s in DOC_STATUSES:
        by_status[s] = await db.documents.count_documents({**scope, "status": s})

    recent_cursor = db.documents.find(
        scope, {"_id": 0, "raw_text": 0, "extracted_data": 0},
    ).sort("created_at", -1).limit(5)
    recent = [_serialize(d) async for d in recent_cursor]

    return {"total": total, "by_type": by_type, "by_status": by_status, "recent": recent}


# ---------------------------------------------------------------------------
# Document upload / process
# ---------------------------------------------------------------------------

async def _save_upload(file: UploadFile, owner: dict) -> Dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    doc_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{doc_id}.pdf"
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)
    doc = DocumentModel(
        id=doc_id, filename=file.filename, file_url=f"/api/documents/{doc_id}/file",
        status="UPLOADED", source="AUTO",
        owner_id=owner["id"], owner_email=owner["email"],
    )
    stored = _serialize(doc.model_dump())
    await db.documents.insert_one(stored)
    stored.pop("_id", None)
    return stored


async def _run_pipeline(doc_id: str) -> None:
    """Synchronous pipeline runner used by both sync & background processing."""
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if not file_path.exists():
        await db.documents.update_one({"id": doc_id}, {"$set": {"status": "FAILED"}})
        return
    try:
        await db.documents.update_one({"id": doc_id}, {"$set": {"status": "PROCESSING"}})
        raw_text, ocr_method = extract_text_from_pdf(file_path)
        doc_type, confidence, method = await classify(raw_text)
        extracted = await extract_structured(doc_type, raw_text)
        now = datetime.now(timezone.utc).isoformat()
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
                "updated_at": now,
            }},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for %s: %s", doc_id, exc)
        await db.documents.update_one({"id": doc_id}, {"$set": {"status": "FAILED"}})


@api_router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(require_min_role("user"))):
    saved = await _save_upload(file, user)
    await log_from_user(
        db, user,
                    action="DOC_UPLOAD", target_type="document", target_id=saved["id"],
                    meta={"filename": saved["filename"]})
    return saved


@api_router.post("/documents/{doc_id}/process")
async def process_document(doc_id: str, user: dict = Depends(require_min_role("user"))):
    existing = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")
    await _run_pipeline(doc_id)
    updated = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    await log_from_user(
        db, user,
                    action="DOC_PROCESS", target_type="document", target_id=doc_id,
                    meta={"type": updated.get("type"), "ocr": updated.get("ocr_method")})
    return _serialize(updated)


def _use_celery() -> bool:
    if os.environ.get("USE_CELERY", "true").lower() not in {"1", "true", "yes"}:
        return False
    try:
        import redis as _redis
        r = _redis.Redis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"))
        r.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _enqueue_pipeline(bg: BackgroundTasks, doc_id: str) -> str:
    """Enqueue the OCR pipeline on Celery when available; else in-process."""
    if _use_celery():
        try:
            from celery_app import process_document_task
            process_document_task.delay(doc_id)
            return "celery"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery enqueue failed (%s); falling back to BackgroundTasks", exc)
    bg.add_task(_run_pipeline, doc_id)
    return "background_task"


@api_router.post("/documents/bulk-upload")
async def bulk_upload(
    bg: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user: dict = Depends(require_min_role("user")),
):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Max 20 files per bulk upload")
    results = []
    runner = "background_task"
    for f in files:
        try:
            saved = await _save_upload(f, user)
            runner = _enqueue_pipeline(bg, saved["id"])
            results.append({"id": saved["id"], "filename": saved["filename"], "queued": True})
        except HTTPException as e:
            results.append({"filename": f.filename, "queued": False, "error": e.detail})

    await log_from_user(
        db, user,
                    action="DOC_BULK_UPLOAD", target_type="document",
                    meta={"count": len(results), "runner": runner})
    return {"queued": sum(1 for r in results if r.get("queued")), "runner": runner, "items": results}


@api_router.get("/admin/queue-status")
async def queue_status(_: dict = Depends(require_roles("admin"))):
    using_celery = _use_celery()
    depth = 0
    if using_celery:
        try:
            import redis as _redis
            r = _redis.Redis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"))
            depth = r.llen("procureflow") or 0
        except Exception:  # noqa: BLE001
            pass
    in_flight = await db.documents.count_documents({"status": "PROCESSING"})
    failed = await db.documents.count_documents({"status": "FAILED"})
    return {
        "celery_available": using_celery,
        "runner": "celery" if using_celery else "background_task",
        "pending_in_redis": depth,
        "in_flight": in_flight,
        "failed": failed,
    }


@api_router.get("/documents/bulk-status")
async def bulk_status(ids: str, user: dict = Depends(get_current_user)):
    id_list = [x for x in ids.split(",") if x]
    scope = {"id": {"$in": id_list}}
    if user["role"] not in {"admin", "manager"}:
        scope["owner_id"] = user["id"]
    cursor = db.documents.find(scope, {"_id": 0, "id": 1, "status": 1, "type": 1, "filename": 1})
    return [d async for d in cursor]


# ---------------------------------------------------------------------------
# Document list / get / review / create / pdf / email / delete
# ---------------------------------------------------------------------------

@api_router.get("/documents")
async def list_documents(
    type: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if type and type.upper() != "ALL":
        query["type"] = type.upper()
    if status and status.upper() != "ALL":
        query["status"] = status.upper()
    if source and source.upper() != "ALL":
        query["source"] = source.upper()
    if user["role"] not in {"admin", "manager"}:
        query["owner_id"] = user["id"]

    if q:
        safe = re.escape(q)
        query["$or"] = [
            {"filename": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.vendor_name": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.client_name": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.po_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.quotation_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.reference_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.request_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.delivery_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.invoice_number": {"$regex": safe, "$options": "i"}},
            {"extracted_data.header.title": {"$regex": safe, "$options": "i"}},
        ]

    total = await db.documents.count_documents(query)
    skip = (page - 1) * page_size
    cursor = (
        db.documents.find(query, {"_id": 0, "raw_text": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    items = [_serialize(d) async for d in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def _get_doc_checked(doc_id: str, user: dict) -> Dict[str, Any]:
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if user["role"] not in {"admin", "manager"} and doc.get("owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="Forbidden")
    return doc


@api_router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: dict = Depends(get_current_user)):
    doc = await _get_doc_checked(doc_id, user)
    return _serialize(doc)


@api_router.put("/documents/{doc_id}/review")
async def review_document(doc_id: str, payload: ReviewPayload, user: dict = Depends(require_min_role("user"))):
    existing = await _get_doc_checked(doc_id, user)
    if payload.status == "FINAL" and user["role"] not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Only manager/admin can finalize")
    updates: Dict[str, Any] = {
        "extracted_data": payload.extracted_data,
        "status": (payload.status or "REVIEWED").upper(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.type:
        updates["type"] = payload.type.upper()
    await db.documents.update_one({"id": doc_id}, {"$set": updates})

    await log_from_user(
        db, user,
                    action="DOC_REVIEW", target_type="document", target_id=doc_id,
                    meta={"status": updates["status"]})
    merged = {**existing, **updates}
    return _serialize(merged)


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_min_role("user"))):
    existing = await _get_doc_checked(doc_id, user)
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    await db.documents.delete_one({"id": doc_id})
    await log_from_user(
        db, user,
                    action="DOC_DELETE", target_type="document", target_id=doc_id,
                    meta={"filename": existing.get("filename")})
    return {"deleted": doc_id}


@api_router.post("/documents/create")
async def create_manual_document(payload: CreateDocumentPayload, user: dict = Depends(require_min_role("user"))):
    tpl = get_template(payload.type)
    if not tpl:
        raise HTTPException(status_code=400, detail="Unknown document type")
    doc = DocumentModel(
        type=payload.type.upper(), status="MANUAL_DRAFT", source="MANUAL",
        extracted_data=payload.data, confidence_score=1.0, classification_method="manual",
        owner_id=user["id"], owner_email=user["email"],
    )
    stored = _serialize(doc.model_dump())
    await db.documents.insert_one(stored)
    stored.pop("_id", None)
    await log_from_user(
        db, user,
                    action="DOC_CREATE_MANUAL", target_type="document", target_id=doc.id,
                    meta={"type": doc.type})
    return doc.model_dump()


@api_router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str, user: dict = Depends(get_current_user)):
    await _get_doc_checked(doc_id, user)
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), media_type="application/pdf", filename=file_path.name)


def _reference_of(doc: Dict[str, Any]) -> str:
    header = (doc.get("extracted_data") or {}).get("header", {})
    for k in ("quotation_number", "po_number", "invoice_number", "request_number", "delivery_number"):
        val = header.get(k)
        if val:
            return str(val)
    return str(doc.get("id", ""))[:8]


def _render_pdf_or_400(doc: Dict[str, Any]) -> bytes:
    try:
        return render_document_pdf(doc.get("type", "OTHER"), doc.get("extracted_data") or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/documents/{doc_id}/pdf")
async def generate_document_pdf(doc_id: str, user: dict = Depends(get_current_user)):
    doc = await _get_doc_checked(doc_id, user)
    pdf_bytes = _render_pdf_or_400(doc)
    return FastResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.get("type", "document")}-{doc_id}.pdf"'},
    )


@api_router.post("/documents/{doc_id}/email")
async def email_document(
    doc_id: str, payload: EmailPayload,
    user: dict = Depends(require_min_role("manager")),
):
    doc = await _get_doc_checked(doc_id, user)
    if not email_configured():
        raise HTTPException(
            status_code=503,
            detail="Email not configured. Set RESEND_API_KEY and RESEND_FROM_EMAIL in backend .env, then restart.",
        )

    pdf_bytes = _render_pdf_or_400(doc)
    ref = _reference_of(doc)
    subject = payload.subject or f"{doc.get('type', 'Document')} {ref}"
    message = payload.message or f"Please find attached {doc.get('type', 'document')} {ref}."

    try:
        result = send_pdf_email(
            to=payload.to, cc=payload.cc,
            subject=subject, message=message,
            pdf_bytes=pdf_bytes,
            filename=f"{doc.get('type', 'document')}-{ref}.pdf",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email send failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Email provider error: {exc}") from exc

    await log_from_user(
        db, user,
        action="DOC_EMAIL", target_type="document", target_id=doc_id,
        meta={"to": payload.to, "ref": ref},
    )
    return {"ok": True, "provider_response": result}


# ---------------------------------------------------------------------------
# Startup: indexes + admin seed
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.documents.create_index("id", unique=True)
    await db.documents.create_index("created_at")
    await db.documents.create_index("owner_id")
    await db.login_attempts.create_index("identifier", unique=True)
    await db.audit_logs.create_index("created_at")
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.document_templates.create_index("document_type", unique=True)

    # Load admin-defined template overrides into the runtime overlay
    await _refresh_templates_from_db()

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_name = os.environ.get("ADMIN_NAME", "Admin")
    if admin_email and admin_password:
        existing = await db.users.find_one({"email": admin_email})
        if not existing:
            await db.users.insert_one(new_user_doc(admin_email, admin_password, admin_name, "admin"))
            logger.info("Seeded admin user %s", admin_email)
        elif not verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_password), "role": "admin"}},
            )
            logger.info("Updated admin password for %s", admin_email)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ---------------------------------------------------------------------------
# Middleware & routes
# ---------------------------------------------------------------------------

app.include_router(api_router)

frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
_raw_cors = os.environ.get("CORS_ORIGINS", "")
cors_origins = (
    [frontend_url] if frontend_url
    else [o.strip() for o in _raw_cors.split(",") if o.strip()]
)
# "allow_origins=['*']" is incompatible with allow_credentials=True — browsers will
# reject the pre-flight and never send/accept cookies.  If neither env var is set we
# fall back to allow_origins=[] (blocks all cross-origin requests) and log a clear
# warning so the misconfiguration is visible in Render logs.
if not cors_origins:
    logger.warning(
        "FRONTEND_URL and CORS_ORIGINS are both unset. "
        "Cross-origin cookie auth will not work. "
        "Set FRONTEND_URL on the backend service to your frontend URL."
    )

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,  # explicit list only — never "*" with credentials
    allow_methods=["*"],
    allow_headers=["*"],
)
