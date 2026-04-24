from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from services.classification_service import classify
from services.extraction_service import extract_structured
from services.ocr_service import extract_text_from_pdf
from services.pdf_service import render_document_pdf
from services.templates import get_template, list_templates

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="ProcureFlow API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("procureflow")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

DOC_STATUSES = ["UPLOADED", "PROCESSING", "EXTRACTED", "REVIEWED", "FINAL", "MANUAL_DRAFT"]
DOC_TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"]
DOC_SOURCES = ["AUTO", "MANUAL"]


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "OTHER"
    status: str = "UPLOADED"
    source: str = "AUTO"  # AUTO (uploaded) or MANUAL (template)
    filename: Optional[str] = None
    file_url: Optional[str] = None  # relative `/api/documents/{id}/file`
    raw_text: Optional[str] = ""
    confidence_score: float = 0.0
    classification_method: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewPayload(BaseModel):
    extracted_data: Dict[str, Any]
    status: Optional[str] = None
    type: Optional[str] = None


class CreateDocumentPayload(BaseModel):
    type: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    for k in ("created_at", "updated_at"):
        v = doc.get(k)
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


def _deserialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    for k in ("created_at", "updated_at"):
        v = doc.get(k)
        if isinstance(v, str):
            try:
                doc[k] = datetime.fromisoformat(v)
            except ValueError:
                pass
    return doc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "ProcureFlow API", "version": "1.0"}


# ---- Templates -----------------------------------------------------------

@api_router.get("/templates")
async def get_templates():
    return {"templates": list_templates()}


@api_router.get("/templates/{doc_type}")
async def get_one_template(doc_type: str):
    tpl = get_template(doc_type)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


# ---- Dashboard -----------------------------------------------------------

@api_router.get("/dashboard/stats")
async def dashboard_stats():
    total = await db.documents.count_documents({})
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for t in DOC_TYPES:
        by_type[t] = await db.documents.count_documents({"type": t})
    for s in DOC_STATUSES:
        by_status[s] = await db.documents.count_documents({"status": s})

    recent_cursor = db.documents.find({}, {"_id": 0, "raw_text": 0, "extracted_data": 0}).sort("created_at", -1).limit(5)
    recent = [_serialize(d) async for d in recent_cursor]

    return {"total": total, "by_type": by_type, "by_status": by_status, "recent": recent}


# ---- Document upload / list / get ---------------------------------------

@api_router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    doc_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{doc_id}.pdf"
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    doc = DocumentModel(
        id=doc_id,
        filename=file.filename,
        file_url=f"/api/documents/{doc_id}/file",
        status="UPLOADED",
        source="AUTO",
    )
    payload = _serialize(doc.model_dump())
    await db.documents.insert_one(payload)
    return doc.model_dump()


@api_router.post("/documents/{doc_id}/process")
async def process_document(doc_id: str):
    existing = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing on storage")

    await db.documents.update_one({"id": doc_id}, {"$set": {"status": "PROCESSING"}})

    raw_text = extract_text_from_pdf(file_path)
    doc_type, confidence, method = await classify(raw_text)
    extracted = await extract_structured(doc_type, raw_text)

    now = datetime.now(timezone.utc).isoformat()
    updates = {
        "raw_text": raw_text,
        "type": doc_type,
        "confidence_score": confidence,
        "classification_method": method,
        "extracted_data": extracted,
        "status": "EXTRACTED",
        "updated_at": now,
    }
    await db.documents.update_one({"id": doc_id}, {"$set": updates})
    merged = {**existing, **updates}
    return _deserialize(merged)


@api_router.get("/documents")
async def list_documents(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    q: Dict[str, Any] = {}
    if type:
        q["type"] = type.upper()
    if status:
        q["status"] = status.upper()
    if source:
        q["source"] = source.upper()

    cursor = db.documents.find(q, {"_id": 0, "raw_text": 0}).sort("created_at", -1).limit(500)
    return [_serialize(d) async for d in cursor]


@api_router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize(doc)


@api_router.put("/documents/{doc_id}/review")
async def review_document(doc_id: str, payload: ReviewPayload):
    existing = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    updates: Dict[str, Any] = {
        "extracted_data": payload.extracted_data,
        "status": payload.status or "REVIEWED",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.type:
        updates["type"] = payload.type.upper()

    await db.documents.update_one({"id": doc_id}, {"$set": updates})
    merged = {**existing, **updates}
    return _serialize(merged)


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    existing = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    await db.documents.delete_one({"id": doc_id})
    return {"deleted": doc_id}


@api_router.post("/documents/create")
async def create_manual_document(payload: CreateDocumentPayload):
    tpl = get_template(payload.type)
    if not tpl:
        raise HTTPException(status_code=400, detail="Unknown document type")

    doc = DocumentModel(
        type=payload.type.upper(),
        status="MANUAL_DRAFT",
        source="MANUAL",
        extracted_data=payload.data,
        confidence_score=1.0,
        classification_method="manual",
    )
    stored = _serialize(doc.model_dump())
    await db.documents.insert_one(stored)
    return doc.model_dump()


@api_router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str):
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), media_type="application/pdf", filename=file_path.name)


@api_router.get("/documents/{doc_id}/pdf")
async def generate_document_pdf(doc_id: str):
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        pdf_bytes = render_document_pdf(doc.get("type", "OTHER"), doc.get("extracted_data") or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.get("type", "document")}-{doc_id}.pdf"'},
    )


# ---------------------------------------------------------------------------
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
