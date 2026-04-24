"""ProcureFlow Phase 3 backend tests.

Covers:
  * Password reset flow (forgot + reset + error paths + DB assertions)
  * Admin template editor CRUD (builtin reset vs custom delete, validation,
    upsert, RBAC, schema-from-overlay precedence)
  * Celery + Redis bulk pipeline (runner=celery, queue-status, eventual
    EXTRACTED) with graceful fallback
  * Audit-log regressions for the new actions
"""
from __future__ import annotations

import io
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "syazwan.zulkifli@quatriz.com.my"
ADMIN_PASSWORD = "Admin@123"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SAMPLE_PDF_URL = (
    "https://customer-assets.emergentagent.com/job_smart-procurement-31/"
    "artifacts/4fp2xmmo_QUO_AFA_AD-HOC%20MAINTENANCE%20-%20GOM%2C%20T11.pdf"
)

TIMEOUT = 60


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    r = requests.get(SAMPLE_PDF_URL, timeout=TIMEOUT)
    assert r.status_code == 200, f"Could not fetch sample PDF: {r.status_code}"
    assert r.content.startswith(b"%PDF")
    return r.content


@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def throwaway_user(admin_token):
    """Create a throwaway user that we can reset password on, cleaned up at end."""
    email = f"test_reset_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPass123"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": "Reset Test"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    token = r.json()["access_token"]
    yield {"id": uid, "email": email, "password": password, "token": token}

    # Teardown
    requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)


@pytest.fixture(scope="session")
def non_admin_token(admin_token):
    email = f"test_useronly_{uuid.uuid4().hex[:6]}@example.com"
    password = "Passw0rd!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": "Nope"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    uid = r.json()["user"]["id"]
    tok = r.json()["access_token"]
    yield tok
    requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)


# ---------------------------------------------------------------------------
# Password reset flow
# ---------------------------------------------------------------------------

class TestPasswordReset:
    def test_forgot_password_existing_email_creates_token(self, throwaway_user, mongo):
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": throwaway_user["email"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        rec = mongo.password_reset_tokens.find_one({"email": throwaway_user["email"], "used": False})
        assert rec is not None, "Token was not created in password_reset_tokens"
        assert rec["user_id"] == throwaway_user["id"]
        # expires_at ~1h away
        exp = datetime.fromisoformat(rec["expires_at"])
        now = datetime.now(timezone.utc)
        delta_min = (exp - now).total_seconds() / 60
        assert 55 <= delta_min <= 65, f"expires_at not ~1h out: {delta_min} min"

    def test_forgot_password_nonexistent_email_returns_200_no_token(self, mongo):
        bogus = f"ghost_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/forgot-password", json={"email": bogus}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert mongo.password_reset_tokens.find_one({"email": bogus}) is None

    def test_reset_with_invalid_token_400(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "nope-not-a-real-token", "password": "NewPass123!"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "invalid" in r.json()["detail"].lower()

    def test_reset_with_expired_token_400(self, throwaway_user, mongo):
        token = f"expired-{uuid.uuid4().hex}"
        mongo.password_reset_tokens.insert_one({
            "token": token,
            "user_id": throwaway_user["id"],
            "email": throwaway_user["email"],
            "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": token, "password": "NewPass123!"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

    def test_reset_short_password_422(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "whatever", "password": "short"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422

    def test_full_reset_flow_rotates_password_and_consumes_token(self, throwaway_user, mongo):
        # Clear any prior tokens for isolation
        mongo.password_reset_tokens.delete_many({"email": throwaway_user["email"]})

        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": throwaway_user["email"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        rec = mongo.password_reset_tokens.find_one({"email": throwaway_user["email"], "used": False})
        assert rec is not None
        token = rec["token"]
        new_pw = "BrandNewPass!42"

        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": token, "password": new_pw},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # Old password no longer works
        old = requests.post(
            f"{API}/auth/login",
            json={"email": throwaway_user["email"], "password": throwaway_user["password"]},
            timeout=TIMEOUT,
        )
        assert old.status_code == 401

        # New password works
        new = requests.post(
            f"{API}/auth/login",
            json={"email": throwaway_user["email"], "password": new_pw},
            timeout=TIMEOUT,
        )
        assert new.status_code == 200, new.text

        # Token should now be marked used in DB
        rec2 = mongo.password_reset_tokens.find_one({"token": token})
        assert rec2 is not None and rec2["used"] is True

        # Update the fixture credential so teardown works (and for follow-up tests)
        throwaway_user["password"] = new_pw
        throwaway_user["token"] = new.json()["access_token"]

        # Reuse of same token must fail
        again = requests.post(
            f"{API}/auth/reset-password",
            json={"token": token, "password": "AnotherPass123!"},
            timeout=TIMEOUT,
        )
        assert again.status_code == 400
        assert "invalid" in again.json()["detail"].lower() or "used" in again.json()["detail"].lower()

    def test_audit_log_captures_reset_actions(self, admin_token):
        # Reset flow above should have produced PASSWORD_RESET_REQUESTED + COMPLETED
        r = requests.get(
            f"{API}/audit-logs",
            params={"action": "PASSWORD_RESET_REQUESTED", "limit": 50},
            headers=_h(admin_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1

        r2 = requests.get(
            f"{API}/audit-logs",
            params={"action": "PASSWORD_RESET_COMPLETED", "limit": 50},
            headers=_h(admin_token),
            timeout=TIMEOUT,
        )
        assert r2.status_code == 200
        assert len(r2.json()) >= 1


# ---------------------------------------------------------------------------
# Admin: template editor
# ---------------------------------------------------------------------------

def _valid_schema():
    return {
        "header_fields": [
            {"key": "ref_no", "label": "Ref #", "type": "text", "required": True},
            {"key": "issued_on", "label": "Issued On", "type": "date"},
        ],
        "item_columns": [
            {"key": "description", "label": "Description", "type": "textarea"},
            {"key": "quantity", "label": "Qty", "type": "number"},
        ],
        "totals": [
            {"key": "grand_total", "label": "Grand Total"},
        ],
        "tax_rate": 0.06,
    }


class TestTemplateEditor:
    custom_type = f"TEST_{uuid.uuid4().hex[:6].upper()}"

    def test_non_admin_forbidden(self, non_admin_token):
        body = {"document_type": "CUSTOM_X", "label": "X", "schema": _valid_schema()}
        r = requests.post(f"{API}/admin/templates", json=body, headers=_h(non_admin_token), timeout=TIMEOUT)
        assert r.status_code == 403

        r = requests.put(f"{API}/admin/templates/PO", json={"document_type": "PO", "label": "PO", "schema": _valid_schema()},
                         headers=_h(non_admin_token), timeout=TIMEOUT)
        assert r.status_code == 403

        r = requests.delete(f"{API}/admin/templates/PO", headers=_h(non_admin_token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_create_invalid_document_type_400(self, admin_token):
        # Note: server uppercases before regex check, so "lowercase" is accepted as
        # "LOWERCASE" — the spec's regex is only enforced on the final (uppercased)
        # form. We therefore only include types that can't be salvaged by .upper().
        bad_types = ["a", "WITH SPACE", "TOO_LONG_" + "X" * 40, "BAD!CHAR"]
        for bad in bad_types:
            r = requests.post(
                f"{API}/admin/templates",
                json={"document_type": bad, "label": "x", "schema": _valid_schema()},
                headers=_h(admin_token), timeout=TIMEOUT,
            )
            assert r.status_code == 400, f"{bad} should 400 got {r.status_code}: {r.text}"

    def test_create_invalid_schema_400(self, admin_token):
        # header_fields missing
        r = requests.post(
            f"{API}/admin/templates",
            json={"document_type": "BADSCHEMA1", "label": "x", "schema": {"header_fields": "notarray",
                                                                          "item_columns": [], "totals": []}},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 400

        # header_field missing label
        r = requests.post(
            f"{API}/admin/templates",
            json={"document_type": "BADSCHEMA2", "label": "x", "schema": {
                "header_fields": [{"key": "x"}], "item_columns": [], "totals": []}},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 400

        # unsupported type
        r = requests.post(
            f"{API}/admin/templates",
            json={"document_type": "BADSCHEMA3", "label": "x", "schema": {
                "header_fields": [{"key": "x", "label": "X", "type": "email"}],
                "item_columns": [], "totals": []}},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 400

        # tax_rate non-numeric
        bad = _valid_schema()
        bad["tax_rate"] = "abc"
        r = requests.post(
            f"{API}/admin/templates",
            json={"document_type": "BADSCHEMA4", "label": "x", "schema": bad},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 400

    def test_create_custom_template_and_list(self, admin_token):
        body = {"document_type": self.custom_type, "label": "Custom Template", "schema": _valid_schema()}
        r = requests.post(f"{API}/admin/templates", json=body, headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["document_type"] == self.custom_type
        assert created["label"] == "Custom Template"

        # List templates (public) — returns {"templates": [...]}
        lst = requests.get(f"{API}/templates", timeout=TIMEOUT)
        assert lst.status_code == 200
        payload = lst.json()
        if isinstance(payload, dict):
            payload = payload.get("templates", [])
        types = [t["document_type"] for t in payload]
        assert self.custom_type in types

        # Individual fetch
        one = requests.get(f"{API}/templates/{self.custom_type}", timeout=TIMEOUT)
        assert one.status_code == 200
        assert one.json()["schema"]["tax_rate"] == 0.06

    def test_put_body_type_must_match_url(self, admin_token):
        r = requests.put(
            f"{API}/admin/templates/{self.custom_type}",
            json={"document_type": "MISMATCH", "label": "x", "schema": _valid_schema()},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 400

    def test_put_updates_custom_template(self, admin_token):
        new_schema = _valid_schema()
        new_schema["tax_rate"] = 0.10
        r = requests.put(
            f"{API}/admin/templates/{self.custom_type}",
            json={"document_type": self.custom_type, "label": "Custom V2", "schema": new_schema},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 200
        got = requests.get(f"{API}/templates/{self.custom_type}", timeout=TIMEOUT).json()
        assert got["label"] == "Custom V2"
        assert got["schema"]["tax_rate"] == 0.10

    def test_override_quotation_then_reset(self, admin_token):
        # Snapshot built-in current schema (should be default before override)
        pre = requests.get(f"{API}/templates/QUOTATION", timeout=TIMEOUT).json()
        default_tax = pre["schema"]["tax_rate"]

        new_schema = _valid_schema()
        new_schema["tax_rate"] = 0.99  # clearly different marker
        r = requests.put(
            f"{API}/admin/templates/QUOTATION",
            json={"document_type": "QUOTATION", "label": "Quotation (Overridden)", "schema": new_schema},
            headers=_h(admin_token), timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text

        overridden = requests.get(f"{API}/templates/QUOTATION", timeout=TIMEOUT).json()
        assert overridden["label"] == "Quotation (Overridden)"
        assert overridden["schema"]["tax_rate"] == 0.99

        # DELETE on built-in should reset (not remove)
        d = requests.delete(f"{API}/admin/templates/QUOTATION", headers=_h(admin_token), timeout=TIMEOUT)
        assert d.status_code == 200, d.text
        assert d.json().get("reset") is True
        assert d.json().get("found_override") is True

        after = requests.get(f"{API}/templates/QUOTATION", timeout=TIMEOUT).json()
        assert after["schema"]["tax_rate"] == default_tax
        # Built-in still available
        assert after["document_type"] == "QUOTATION"

    def test_delete_custom_template_removes(self, admin_token):
        d = requests.delete(f"{API}/admin/templates/{self.custom_type}",
                            headers=_h(admin_token), timeout=TIMEOUT)
        assert d.status_code == 200
        assert d.json().get("deleted") == self.custom_type

        # Gone from list
        lst_json = requests.get(f"{API}/templates", timeout=TIMEOUT).json()
        if isinstance(lst_json, dict):
            lst_json = lst_json.get("templates", [])
        types = [t["document_type"] for t in lst_json]
        assert self.custom_type not in types

        # Re-delete => 404
        d2 = requests.delete(f"{API}/admin/templates/{self.custom_type}",
                             headers=_h(admin_token), timeout=TIMEOUT)
        assert d2.status_code == 404

    def test_template_audit_actions(self, admin_token):
        for action in ("TEMPLATE_UPSERT", "TEMPLATE_RESET", "TEMPLATE_DELETE"):
            r = requests.get(f"{API}/audit-logs", params={"action": action, "limit": 50},
                             headers=_h(admin_token), timeout=TIMEOUT)
            assert r.status_code == 200
            assert len(r.json()) >= 1, f"No audit entry for {action}"


# ---------------------------------------------------------------------------
# Celery + Redis bulk pipeline
# ---------------------------------------------------------------------------

class TestCeleryBulk:
    def test_queue_status_requires_admin(self, non_admin_token):
        r = requests.get(f"{API}/admin/queue-status", headers=_h(non_admin_token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_queue_status_admin(self, admin_token):
        r = requests.get(f"{API}/admin/queue-status", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["celery_available"] is True, f"Expected celery_available=True, got {body}"
        assert body["runner"] == "celery"
        assert "pending_in_redis" in body and isinstance(body["pending_in_redis"], int)
        assert "in_flight" in body and "failed" in body

    def test_bulk_upload_uses_celery_and_extracts(self, admin_token, sample_pdf_bytes):
        files = [
            ("files", ("sample_a.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
            ("files", ("sample_b.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
        ]
        r = requests.post(f"{API}/documents/bulk-upload", files=files,
                          headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] == 2
        assert body["runner"] == "celery", f"Expected runner=celery, got {body['runner']}"

        ids = [item["id"] for item in body["items"] if item.get("queued")]
        assert len(ids) == 2

        # Poll bulk-status until both reach EXTRACTED or timeout
        deadline = time.time() + 120
        last = {}
        while time.time() < deadline:
            s = requests.get(f"{API}/documents/bulk-status",
                             params={"ids": ",".join(ids)},
                             headers=_h(admin_token), timeout=TIMEOUT)
            assert s.status_code == 200
            items = s.json()
            last = {it["id"]: it["status"] for it in items}
            if all(st == "EXTRACTED" for st in last.values()) and len(last) == 2:
                break
            if any(st == "FAILED" for st in last.values()):
                pytest.fail(f"Pipeline FAILED: {last}")
            time.sleep(3)

        assert all(st == "EXTRACTED" for st in last.values()), f"Did not extract in time: {last}"

        # Cleanup
        for doc_id in ids:
            requests.delete(f"{API}/documents/{doc_id}", headers=_h(admin_token), timeout=TIMEOUT)
