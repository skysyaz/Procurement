"""ProcureFlow API regression tests - covers templates, dashboard, upload,
process (OCR+LLM extraction), review, manual create, PDF generation, file fetch and delete."""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://smart-procurement-31.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
SAMPLE_PDF = "/tmp/sample_quotation.pdf"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    return s


@pytest.fixture(scope="session")
def created_ids():
    return {"uploaded": None, "manual": None}


# ---- Root -------------------------------------------------------------
def test_root(client):
    r = client.get(f"{API}/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "ProcureFlow" in data["message"]


# ---- Templates --------------------------------------------------------
def test_list_templates(client):
    r = client.get(f"{API}/templates")
    assert r.status_code == 200
    body = r.json()
    assert "templates" in body
    tpls = body["templates"]
    types = {t.get("document_type") or t.get("type") or t.get("doc_type") for t in tpls}
    # Must include PO, PR, DO, QUOTATION
    assert {"PO", "PR", "DO", "QUOTATION"}.issubset(types), f"Got types: {types}"
    for t in tpls:
        schema = t.get("schema", {})
        assert "header_fields" in schema
        assert "item_columns" in schema
        assert "totals" in schema
        assert "tax_rate" in schema


def test_get_quotation_template(client):
    r = client.get(f"{API}/templates/QUOTATION")
    assert r.status_code == 200
    data = r.json()
    schema = data.get("schema", {})
    assert "header_fields" in schema and isinstance(schema["header_fields"], list)
    assert "item_columns" in schema
    assert "totals" in schema
    assert "tax_rate" in schema


def test_get_unknown_template_404(client):
    r = client.get(f"{API}/templates/UNKNOWN")
    assert r.status_code == 404


# ---- Dashboard --------------------------------------------------------
def test_dashboard_stats(client):
    r = client.get(f"{API}/dashboard/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("total", "by_type", "by_status", "recent"):
        assert key in data
    assert isinstance(data["total"], int)
    assert isinstance(data["by_type"], dict)
    assert isinstance(data["by_status"], dict)
    assert isinstance(data["recent"], list)
    # Key types present
    assert "QUOTATION" in data["by_type"]
    assert "UPLOADED" in data["by_status"]


# ---- Upload validation ------------------------------------------------
def test_upload_non_pdf_rejected(client):
    files = {"file": ("notes.txt", b"hello world", "text/plain")}
    r = client.post(f"{API}/documents/upload", files=files)
    assert r.status_code == 400


# ---- Upload + process full flow --------------------------------------
def test_upload_pdf(client, created_ids):
    assert os.path.exists(SAMPLE_PDF), "sample pdf missing"
    with open(SAMPLE_PDF, "rb") as fh:
        files = {"file": ("sample_quotation.pdf", fh, "application/pdf")}
        r = client.post(f"{API}/documents/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "UPLOADED"
    assert data["source"] == "AUTO"
    assert data["id"]
    assert data["file_url"] == f"/api/documents/{data['id']}/file"
    created_ids["uploaded"] = data["id"]


def test_process_non_existent_404(client):
    r = client.post(f"{API}/documents/{uuid.uuid4()}/process")
    assert r.status_code == 404


def test_process_uploaded_pdf(client, created_ids):
    doc_id = created_ids.get("uploaded")
    assert doc_id, "Previous upload failed"
    r = client.post(f"{API}/documents/{doc_id}/process", timeout=180)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "EXTRACTED"
    assert data["type"] == "QUOTATION", f"classified as {data['type']}"
    extracted = data.get("extracted_data") or {}
    header = extracted.get("header") or {}
    # Quotation number should carry company tag - loose check
    # LLM sometimes puts the quotation id into reference_number instead; accept either
    qn = str(header.get("quotation_number", "")).upper()
    ref = str(header.get("reference_number", "")).upper()
    assert qn or ref, f"no quotation/reference number extracted; header={header}"
    assert ("QSSB" in qn) or ("QSSB" in ref), f"expected QSSB in quotation/reference; got qn={qn} ref={ref}"
    items = extracted.get("items") or []
    assert len(items) >= 1, f"no items extracted: {extracted}"
    totals = extracted.get("totals") or {}
    for k in ("subtotal", "tax", "grand_total"):
        assert k in totals, f"totals missing {k}: {totals}"


# ---- Get / list / filter ---------------------------------------------
def test_get_document(client, created_ids):
    doc_id = created_ids["uploaded"]
    r = client.get(f"{API}/documents/{doc_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == doc_id
    assert "extracted_data" in data


def test_list_documents_and_filters(client, created_ids):
    r = client.get(f"{API}/documents")
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list)
    assert any(d["id"] == created_ids["uploaded"] for d in lst)

    r = client.get(f"{API}/documents", params={"type": "QUOTATION"})
    assert r.status_code == 200
    for d in r.json():
        assert d["type"] == "QUOTATION"

    r = client.get(f"{API}/documents", params={"status": "EXTRACTED"})
    assert r.status_code == 200
    for d in r.json():
        assert d["status"] == "EXTRACTED"


# ---- Review -----------------------------------------------------------
def test_review_document(client, created_ids):
    doc_id = created_ids["uploaded"]
    # Fetch current extracted_data
    cur = client.get(f"{API}/documents/{doc_id}").json()
    ed = cur.get("extracted_data") or {}
    ed.setdefault("header", {})["reviewed_marker"] = "TEST_REVIEW"
    r = client.put(f"{API}/documents/{doc_id}/review", json={"extracted_data": ed})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "REVIEWED"
    assert data["extracted_data"]["header"]["reviewed_marker"] == "TEST_REVIEW"

    # Test explicit FINAL status
    r2 = client.put(f"{API}/documents/{doc_id}/review", json={"extracted_data": ed, "status": "FINAL"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "FINAL"


# ---- Manual create + PDF ---------------------------------------------
def test_create_manual_po(client, created_ids):
    payload = {
        "type": "PO",
        "data": {
            "header": {
                "po_number": "TEST_PO_001",
                "po_date": "2026-01-01",
                "vendor_name": "TEST Vendor",
                "buyer_name": "TEST Buyer",
            },
            "items": [
                {"description": "Widget", "quantity": 2, "unit_price": 10.0, "amount": 20.0}
            ],
            "totals": {"subtotal": 20.0, "tax": 1.2, "grand_total": 21.2},
        },
    }
    r = client.post(f"{API}/documents/create", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "PO"
    assert data["source"] == "MANUAL"
    assert data["status"] == "MANUAL_DRAFT"
    created_ids["manual"] = data["id"]


def test_generate_pdf_manual(client, created_ids):
    doc_id = created_ids["manual"]
    assert doc_id
    r = client.get(f"{API}/documents/{doc_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 500
    assert r.content[:4] == b"%PDF"


def test_get_original_file(client, created_ids):
    doc_id = created_ids["uploaded"]
    r = client.get(f"{API}/documents/{doc_id}/file")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


# ---- Delete -----------------------------------------------------------
def test_delete_manual(client, created_ids):
    doc_id = created_ids["manual"]
    r = client.delete(f"{API}/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] == doc_id
    r2 = client.get(f"{API}/documents/{doc_id}")
    assert r2.status_code == 404


def test_delete_uploaded(client, created_ids):
    doc_id = created_ids["uploaded"]
    r = client.delete(f"{API}/documents/{doc_id}")
    assert r.status_code == 200
    # file should be gone
    r2 = client.get(f"{API}/documents/{doc_id}/file")
    assert r2.status_code == 404
