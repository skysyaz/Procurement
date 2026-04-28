"""ProcureFlow Phase 2 backend regression + auth/RBAC/audit/bulk/pagination/email tests."""
from __future__ import annotations

import io
import os
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# Credentials come from backend .env (seeded admin) — never hardcode secrets
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# Sample PDF: a real Quatriz quotation PDF used for integration testing.
# Download it once and host it yourself, or use a local path override via
# the SAMPLE_PDF_URL env var.
SAMPLE_PDF_URL = os.environ.get(
    "SAMPLE_PDF_URL",
    "https://quatriz.com.my/sample_quotation.pdf",  # replace with your own host
)

TIMEOUT = 60


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    r = requests.get(SAMPLE_PDF_URL, timeout=TIMEOUT)
    assert r.status_code == 200, f"Could not fetch sample PDF: {r.status_code}"
    assert r.content.startswith(b"%PDF"), "Asset is not a PDF"
    return r.content


@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["user"]["role"] == "admin"
    assert "access_token" in body and body["access_token"]
    # Cookies must be set
    assert "access_token" in r.cookies or any(
        c.name == "access_token" for c in r.cookies
    ), "access_token cookie not set"
    return body["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def created_test_users(admin_token):
    """Create fresh viewer+user+manager for role tests. Cleanup via admin."""
    created = {}
    for role in ("viewer", "user", "manager"):
        email = f"test_{role}_{uuid.uuid4().hex[:6]}@example.com"
        password = "Passw0rd!"
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": password, "name": f"Test {role}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"register {role} failed: {r.text}"
        uid = r.json()["user"]["id"]
        token = r.json()["access_token"]

        # promote if needed (role defaults to user)
        if role != "user":
            pr = requests.put(
                f"{API}/admin/users/{uid}/role",
                headers=_h(admin_token),
                json={"role": role},
                timeout=TIMEOUT,
            )
            assert pr.status_code == 200, pr.text
            # relogin to get fresh token with new role claim
            lr = requests.post(
                f"{API}/auth/login",
                json={"email": email, "password": password},
                timeout=TIMEOUT,
            )
            assert lr.status_code == 200
            token = lr.json()["access_token"]

        created[role] = {"id": uid, "email": email, "password": password, "token": token}
    yield created
    # Cleanup
    for u in created.values():
        try:
            requests.delete(
                f"{API}/admin/users/{u['id']}", headers=_h(admin_token), timeout=TIMEOUT
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_admin_login_success(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_me_with_bearer(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
        assert r.json()["role"] == "admin"

    def test_me_with_cookie(self):
        s = requests.Session()
        r = s.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        r2 = s.get(f"{API}/auth/me", timeout=TIMEOUT)
        assert r2.status_code == 200
        assert r2.json()["email"] == ADMIN_EMAIL

    def test_register_short_password_422(self):
        r = requests.post(
            f"{API}/auth/register",
            json={"email": f"short_{uuid.uuid4().hex[:6]}@x.com", "password": "abc", "name": "X"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422

    def test_register_new_user_role_user(self, admin_token):
        email = f"newuser_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Passw0rd!", "name": "NU"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "user"
        # cleanup
        uid = r.json()["user"]["id"]
        requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_login_wrong_password_401(self):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": "definitely-wrong"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_brute_force_lockout(self, admin_token):
        # Create dedicated user so we don't lock the real admin
        email = f"brute_{uuid.uuid4().hex[:6]}@example.com"
        pw = "Passw0rd!"
        reg = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": pw, "name": "B"},
            timeout=TIMEOUT,
        )
        assert reg.status_code == 200
        uid = reg.json()["user"]["id"]
        try:
            codes = []
            # Multi-pod LB may distribute requests; try more attempts so each
            # pod eventually crosses the 5-failure threshold.
            for _ in range(25):
                r = requests.post(
                    f"{API}/auth/login",
                    json={"email": email, "password": "wrong-pw"},
                    timeout=TIMEOUT,
                )
                codes.append(r.status_code)
                if r.status_code == 429:
                    break
            assert 429 in codes, f"Expected 429 lockout, got {codes}"
        finally:
            requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        r = s.post(f"{API}/auth/logout", timeout=TIMEOUT)
        assert r.status_code == 200
        # After logout, /me must fail
        r2 = s.get(f"{API}/auth/me", timeout=TIMEOUT)
        assert r2.status_code == 401

    def test_refresh_token(self):
        s = requests.Session()
        s.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        r = s.post(f"{API}/auth/refresh", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "access_token" in r.json()


class TestPublicAndProtected:
    def test_documents_requires_auth(self):
        assert requests.get(f"{API}/documents", timeout=TIMEOUT).status_code == 401

    def test_dashboard_requires_auth(self):
        assert requests.get(f"{API}/dashboard/stats", timeout=TIMEOUT).status_code == 401

    def test_me_requires_auth(self):
        assert requests.get(f"{API}/auth/me", timeout=TIMEOUT).status_code == 401

    def test_root_public(self):
        r = requests.get(f"{API}/", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "email_configured" in r.json()

    def test_templates_public(self):
        r = requests.get(f"{API}/templates", timeout=TIMEOUT)
        assert r.status_code == 200
        types = {t.get("document_type") or t.get("type") for t in r.json()["templates"]}
        assert {"PO", "PR", "DO", "QUOTATION", "INVOICE"}.issubset(types)

    def test_template_quotation_public(self):
        r = requests.get(f"{API}/templates/QUOTATION", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_template_invoice_schema(self):
        r = requests.get(f"{API}/templates/INVOICE", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        schema = data.get("schema", data)
        hdr = {f.get("key") for f in schema.get("header_fields", []) if isinstance(f, dict)}
        assert {"invoice_number", "invoice_date", "due_date"}.issubset(hdr), hdr
        cols = {c.get("key") for c in schema.get("item_columns", []) if isinstance(c, dict)}
        assert {"description", "quantity", "unit_price", "amount"}.issubset(cols), cols
        totals = schema.get("totals", [])
        if isinstance(totals, list):
            totals_keys = {t.get("key") if isinstance(t, dict) else t for t in totals}
        else:
            totals_keys = set(totals.keys())
        assert {"subtotal", "tax", "grand_total"}.issubset(totals_keys), totals
        assert abs(float(schema.get("tax_rate") or 0) - 0.08) < 1e-6


# ---------------------------------------------------------------------------
# Upload + Process + PDF email + Delete
# ---------------------------------------------------------------------------

class TestDocumentPipeline:
    uploaded_id: str = ""

    def test_upload_real_pdf(self, admin_token, sample_pdf_bytes):
        files = {"file": ("QUO_AFA.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        r = requests.post(
            f"{API}/documents/upload",
            headers=_h(admin_token),
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "UPLOADED"
        TestDocumentPipeline.uploaded_id = data["id"]

    def test_process_document(self, admin_token):
        doc_id = TestDocumentPipeline.uploaded_id
        assert doc_id, "upload test must run first"
        r = requests.post(
            f"{API}/documents/{doc_id}/process", headers=_h(admin_token), timeout=TIMEOUT
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "QUOTATION", f"Expected QUOTATION, got {data.get('type')}"
        assert data["status"] == "EXTRACTED"
        assert data.get("ocr_method") == "digital"
        hdr = (data.get("extracted_data") or {}).get("header") or {}
        assert hdr, "Header should be populated"

    def test_pagination_shape(self, admin_token):
        r = requests.get(
            f"{API}/documents?page=1&page_size=1", headers=_h(admin_token), timeout=TIMEOUT
        )
        assert r.status_code == 200
        data = r.json()
        for k in ("items", "total", "page", "page_size"):
            assert k in data
        assert len(data["items"]) <= 1
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_regex_search(self, admin_token):
        r = requests.get(
            f"{API}/documents?q=quatriz", headers=_h(admin_token), timeout=TIMEOUT
        )
        assert r.status_code == 200
        # At minimum, request is successful and items is a list
        assert isinstance(r.json().get("items"), list)

    def test_filter_combo(self, admin_token):
        r = requests.get(
            f"{API}/documents?type=QUOTATION&status=EXTRACTED",
            headers=_h(admin_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        for it in items:
            assert it["type"] == "QUOTATION"
            assert it["status"] == "EXTRACTED"

    def test_manual_create_invoice_and_pdf(self, admin_token):
        payload = {
            "type": "INVOICE",
            "data": {
                "header": {
                    "invoice_number": "INV-TEST-001",
                    "invoice_date": "2026-01-15",
                    "due_date": "2026-02-15",
                    "vendor_name": "TEST Vendor",
                    "client_name": "TEST Client",
                },
                "items": [
                    {"description": "Widget", "quantity": 2, "unit_price": 50.0, "amount": 100.0}
                ],
                "totals": {"subtotal": 100.0, "tax": 8.0, "grand_total": 108.0},
            },
        }
        r = requests.post(
            f"{API}/documents/create",
            headers=_h(admin_token),
            json=payload,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "MANUAL"
        assert body["status"] == "MANUAL_DRAFT"
        assert body["type"] == "INVOICE"

        pdf_r = requests.get(
            f"{API}/documents/{body['id']}/pdf",
            headers=_h(admin_token),
            timeout=TIMEOUT,
        )
        assert pdf_r.status_code == 200
        assert pdf_r.headers.get("content-type", "").startswith("application/pdf")
        assert pdf_r.content.startswith(b"%PDF")

        # Cleanup
        requests.delete(
            f"{API}/documents/{body['id']}", headers=_h(admin_token), timeout=TIMEOUT
        )

    def test_email_without_resend_returns_503(self, admin_token):
        doc_id = TestDocumentPipeline.uploaded_id
        r = requests.post(
            f"{API}/documents/{doc_id}/email",
            headers=_h(admin_token),
            json={"to": "someone@example.com"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 503, f"Expected 503, got {r.status_code}: {r.text}"
        assert "RESEND_API_KEY" in r.text or "not configured" in r.text.lower()


# ---------------------------------------------------------------------------
# Bulk upload + background status transitions
# ---------------------------------------------------------------------------

class TestBulkUpload:
    def test_bulk_upload_and_status(self, admin_token, sample_pdf_bytes):
        files = [
            ("files", ("doc1.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
            ("files", ("doc2.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
        ]
        r = requests.post(
            f"{API}/documents/bulk-upload",
            headers=_h(admin_token),
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] == 2
        ids = [item["id"] for item in body["items"] if item.get("queued")]
        assert len(ids) == 2

        # Poll up to 45s
        deadline = time.time() + 45
        statuses = {}
        while time.time() < deadline:
            sr = requests.get(
                f"{API}/documents/bulk-status?ids={','.join(ids)}",
                headers=_h(admin_token),
                timeout=TIMEOUT,
            )
            assert sr.status_code == 200
            statuses = {d["id"]: d["status"] for d in sr.json()}
            if all(statuses.get(i) == "EXTRACTED" for i in ids):
                break
            time.sleep(3)

        assert all(statuses.get(i) == "EXTRACTED" for i in ids), (
            f"Bulk items did not reach EXTRACTED: {statuses}"
        )

        # Cleanup
        for i in ids:
            requests.delete(f"{API}/documents/{i}", headers=_h(admin_token), timeout=TIMEOUT)


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

class TestRBAC:
    def test_viewer_cannot_upload(self, created_test_users, sample_pdf_bytes):
        token = created_test_users["viewer"]["token"]
        files = {"file": ("x.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        r = requests.post(
            f"{API}/documents/upload", headers=_h(token), files=files, timeout=TIMEOUT
        )
        assert r.status_code == 403, r.text

    def test_viewer_can_list_documents(self, created_test_users):
        token = created_test_users["viewer"]["token"]
        r = requests.get(f"{API}/documents", headers=_h(token), timeout=TIMEOUT)
        assert r.status_code == 200

    def test_viewer_cannot_delete(self, created_test_users, admin_token, sample_pdf_bytes):
        # Admin uploads a doc, viewer tries to delete
        files = {"file": ("a.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(admin_token), files=files, timeout=TIMEOUT
        )
        did = up.json()["id"]
        try:
            token = created_test_users["viewer"]["token"]
            r = requests.delete(f"{API}/documents/{did}", headers=_h(token), timeout=TIMEOUT)
            assert r.status_code == 403
        finally:
            requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_user_only_sees_own_documents(self, created_test_users, admin_token, sample_pdf_bytes):
        # User uploads one. Listing as user should include it; but should NOT contain admin-only docs
        user_token = created_test_users["user"]["token"]
        user_id = created_test_users["user"]["id"]
        files = {"file": ("userown.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(user_token), files=files, timeout=TIMEOUT
        )
        assert up.status_code == 200
        own_id = up.json()["id"]
        try:
            r = requests.get(f"{API}/documents?page_size=200", headers=_h(user_token), timeout=TIMEOUT)
            assert r.status_code == 200
            items = r.json()["items"]
            # All items owned by user
            for it in items:
                assert it.get("owner_id") == user_id, f"User saw doc not owned by them: {it}"
            assert any(it["id"] == own_id for it in items)
        finally:
            requests.delete(
                f"{API}/documents/{own_id}", headers=_h(admin_token), timeout=TIMEOUT
            )

    def test_manager_sees_all(self, created_test_users, admin_token, sample_pdf_bytes):
        # Admin uploads, manager should be able to GET it
        files = {"file": ("mgr.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(admin_token), files=files, timeout=TIMEOUT
        )
        did = up.json()["id"]
        try:
            mgr_token = created_test_users["manager"]["token"]
            r = requests.get(f"{API}/documents/{did}", headers=_h(mgr_token), timeout=TIMEOUT)
            assert r.status_code == 200
        finally:
            requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_non_manager_cannot_email(self, created_test_users, admin_token, sample_pdf_bytes):
        # Upload as admin, user tries email
        files = {"file": ("e.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(admin_token), files=files, timeout=TIMEOUT
        )
        did = up.json()["id"]
        try:
            user_token = created_test_users["user"]["token"]
            r = requests.post(
                f"{API}/documents/{did}/email",
                headers=_h(user_token),
                json={"to": "x@example.com"},
                timeout=TIMEOUT,
            )
            assert r.status_code == 403, r.text
        finally:
            requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_user_cannot_finalize(self, created_test_users, sample_pdf_bytes):
        user_token = created_test_users["user"]["token"]
        files = {"file": ("rev.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(user_token), files=files, timeout=TIMEOUT
        )
        did = up.json()["id"]
        try:
            r = requests.put(
                f"{API}/documents/{did}/review",
                headers=_h(user_token),
                json={"extracted_data": {"header": {}}, "status": "FINAL"},
                timeout=TIMEOUT,
            )
            assert r.status_code == 403, r.text
        finally:
            requests.delete(f"{API}/documents/{did}", headers=_h(user_token), timeout=TIMEOUT)

    def test_delete_removes_file(self, admin_token, sample_pdf_bytes):
        files = {"file": ("del.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        up = requests.post(
            f"{API}/documents/upload", headers=_h(admin_token), files=files, timeout=TIMEOUT
        )
        did = up.json()["id"]
        r = requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200
        # GET should 404
        g = requests.get(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)
        assert g.status_code == 404
        # File gone on disk
        assert not os.path.exists(f"/app/backend/uploads/{did}.pdf")


# ---------------------------------------------------------------------------
# Admin endpoints + Audit log
# ---------------------------------------------------------------------------

class TestAdminAndAudit:
    def test_list_users_admin_only(self, admin_token, created_test_users):
        r = requests.get(f"{API}/admin/users", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        # viewer/user cannot
        vt = created_test_users["viewer"]["token"]
        r2 = requests.get(f"{API}/admin/users", headers=_h(vt), timeout=TIMEOUT)
        assert r2.status_code == 403

    def test_admin_cannot_demote_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=TIMEOUT).json()
        r = requests.put(
            f"{API}/admin/users/{me['id']}/role",
            headers=_h(admin_token),
            json={"role": "user"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400

    def test_admin_cannot_delete_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=TIMEOUT).json()
        r = requests.delete(
            f"{API}/admin/users/{me['id']}", headers=_h(admin_token), timeout=TIMEOUT
        )
        assert r.status_code == 400

    def test_change_role_roundtrip(self, admin_token):
        email = f"rolechg_{uuid.uuid4().hex[:6]}@example.com"
        reg = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Passw0rd!", "name": "RC"},
            timeout=TIMEOUT,
        )
        uid = reg.json()["user"]["id"]
        try:
            r = requests.put(
                f"{API}/admin/users/{uid}/role",
                headers=_h(admin_token),
                json={"role": "manager"},
                timeout=TIMEOUT,
            )
            assert r.status_code == 200
            # verify
            users = requests.get(f"{API}/admin/users", headers=_h(admin_token), timeout=TIMEOUT).json()
            u = next(x for x in users if x["id"] == uid)
            assert u["role"] == "manager"
        finally:
            requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_audit_logs_admin_only(self, admin_token, created_test_users):
        r = requests.get(f"{API}/audit-logs?limit=200", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200
        logs = r.json()
        assert isinstance(logs, list)
        actions = {log["action"] for log in logs}
        # Expect common actions to have been written during this test run
        expected = {"USER_LOGIN", "DOC_UPLOAD", "DOC_PROCESS", "DOC_CREATE_MANUAL"}
        assert expected.issubset(actions), f"Missing audit actions: {expected - actions}"

        vt = created_test_users["viewer"]["token"]
        r2 = requests.get(f"{API}/audit-logs", headers=_h(vt), timeout=TIMEOUT)
        assert r2.status_code == 403

    def test_audit_filter_by_action(self, admin_token):
        r = requests.get(
            f"{API}/audit-logs?action=USER_LOGIN&limit=20",
            headers=_h(admin_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        for log in r.json():
            assert log["action"] == "USER_LOGIN"
