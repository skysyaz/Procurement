"""ProcureFlow Phase 4 hardening tests.

Focuses on the code-review hardening pass:
  * Cookie-only auth flow works end-to-end (Bearer not required)
  * Bearer header still accepted (backwards compat)
  * AuditEvent refactor: USER_REGISTER + PASSWORD_RESET_COMPLETED write actor_* fields
  * TemplatePayload alias: API contract still accepts {"schema": {...}}
  * Email endpoint: 503 when Resend unconfigured (undefined-var safety)
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

TIMEOUT = 60


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Cookie-only login (Bearer removed from frontend)
# ---------------------------------------------------------------------------

class TestCookieOnlyAuth:
    def test_login_sets_httponly_cookies(self):
        s = requests.Session()
        r = s.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        # access_token and refresh_token must be in cookie jar
        cookie_names = {c.name for c in s.cookies}
        assert "access_token" in cookie_names, cookie_names
        assert "refresh_token" in cookie_names, cookie_names

        # Verify HttpOnly flag on the raw Set-Cookie headers
        set_cookies = r.headers.get("set-cookie") or ""
        # Some servers emit multiple set-cookie headers; use raw.headers
        raw_cookies = r.raw.headers.getlist("set-cookie") if hasattr(r.raw, "headers") else [set_cookies]
        joined = "; ".join(raw_cookies).lower()
        assert "httponly" in joined, f"HttpOnly not set: {raw_cookies}"

    def test_me_works_with_cookie_only_no_bearer(self):
        """The main hardening assertion: login -> hit /me with ONLY the cookie jar (no Bearer)."""
        s = requests.Session()
        login = s.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert login.status_code == 200
        # Explicitly assert no Authorization header is being sent
        r = s.get(f"{API}/auth/me", timeout=TIMEOUT)
        assert "Authorization" not in s.headers
        assert r.status_code == 200, r.text
        assert r.json()["email"] == ADMIN_EMAIL

    def test_bearer_still_accepted_backwards_compat(self, admin_token):
        # Fresh session, no cookies — only Authorization header
        r = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_login_response_body_still_includes_access_token(self):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body and isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 20


# ---------------------------------------------------------------------------
# AuditEvent refactor — actor_* fields populated
# ---------------------------------------------------------------------------

class TestAuditEventRefactor:
    def test_user_register_audit_has_actor_fields(self, admin_token):
        email = f"audit_reg_{uuid.uuid4().hex[:8]}@example.com"
        reg = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Passw0rd!", "name": "AuditReg"},
            timeout=TIMEOUT,
        )
        assert reg.status_code == 200
        uid = reg.json()["user"]["id"]
        try:
            logs = requests.get(
                f"{API}/audit-logs",
                params={"action": "USER_REGISTER", "limit": 100},
                headers=_h(admin_token),
                timeout=TIMEOUT,
            )
            assert logs.status_code == 200
            rows = logs.json()
            match = next((r for r in rows if (r.get("actor_email") or "").lower() == email.lower()), None)
            assert match is not None, f"No USER_REGISTER audit row for {email}. Rows sample: {rows[:3]}"
            # actor_id + actor_email populated
            assert match.get("actor_id") == uid, match
            assert (match.get("actor_email") or "").lower() == email.lower()
            assert match.get("action") == "USER_REGISTER"
        finally:
            requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)

    def test_password_reset_completed_writes_actor_via_write_log(self, admin_token):
        """Covers write_log direct-usage path (not log_from_user)."""
        # Create throwaway user
        email = f"audit_reset_{uuid.uuid4().hex[:8]}@example.com"
        reg = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "InitialPass123", "name": "AuditReset"},
            timeout=TIMEOUT,
        )
        assert reg.status_code == 200
        uid = reg.json()["user"]["id"]
        try:
            # Trigger forgot + reset
            f = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=TIMEOUT)
            assert f.status_code == 200

            # Pull the token from the DB via admin logs? Easier: pymongo
            from pymongo import MongoClient
            mc = MongoClient(os.environ["MONGO_URL"])
            db = mc[os.environ["DB_NAME"]]
            rec = db.password_reset_tokens.find_one({"email": email, "used": False})
            assert rec is not None
            token = rec["token"]
            mc.close()

            rp = requests.post(
                f"{API}/auth/reset-password",
                json={"token": token, "password": "NewPass12345"},
                timeout=TIMEOUT,
            )
            assert rp.status_code == 200, rp.text

            logs = requests.get(
                f"{API}/audit-logs",
                params={"action": "PASSWORD_RESET_COMPLETED", "limit": 100},
                headers=_h(admin_token),
                timeout=TIMEOUT,
            )
            assert logs.status_code == 200
            rows = logs.json()
            match = next(
                (r for r in rows if r.get("actor_id") == uid or (r.get("actor_email") or "").lower() == email.lower()),
                None,
            )
            assert match is not None, f"PASSWORD_RESET_COMPLETED missing for {email}"
            assert match.get("actor_id") == uid
            assert (match.get("actor_email") or "").lower() == email.lower()
        finally:
            requests.delete(f"{API}/admin/users/{uid}", headers=_h(admin_token), timeout=TIMEOUT)


# ---------------------------------------------------------------------------
# TemplatePayload alias — "schema" JSON key still works after field rename
# ---------------------------------------------------------------------------

class TestTemplatePayloadAlias:
    def test_create_template_with_literal_schema_key(self, admin_token):
        doc_type = f"ALIAS{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "document_type": doc_type,
            "label": "Alias Test",
            "schema": {  # literal 'schema' JSON key — must still be accepted
                "header_fields": [{"key": "ref", "label": "Ref", "type": "text"}],
                "item_columns": [{"key": "desc", "label": "Desc", "type": "text"}],
                "totals": [{"key": "grand_total", "label": "Total"}],
                "tax_rate": 0.05,
            },
        }
        r = requests.post(f"{API}/admin/templates", json=payload,
                          headers=_h(admin_token), timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["document_type"] == doc_type
        # Either 'schema' or 'template_schema' must come back with the data
        schema = body.get("schema") or body.get("template_schema")
        assert schema is not None, body
        assert abs(float(schema["tax_rate"]) - 0.05) < 1e-6

        # Cleanup
        d = requests.delete(f"{API}/admin/templates/{doc_type}",
                            headers=_h(admin_token), timeout=TIMEOUT)
        assert d.status_code == 200


# ---------------------------------------------------------------------------
# Email endpoint undefined-var safety (pdf_bytes / result)
# ---------------------------------------------------------------------------

class TestEmailEndpointSafety:
    def test_email_unconfigured_returns_503(self, admin_token):
        # Upload a tiny pdf to email
        import io
        # Minimal valid PDF
        pdf = (
            b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        )
        # Use a real sample so process/pdf path is exercised if needed
        files = {"file": ("tiny.pdf", io.BytesIO(pdf), "application/pdf")}
        up = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                           files=files, timeout=TIMEOUT)
        assert up.status_code == 200, up.text
        did = up.json()["id"]
        try:
            r = requests.post(
                f"{API}/documents/{did}/email",
                headers=_h(admin_token),
                json={"to": "someone@example.com"},
                timeout=TIMEOUT,
            )
            assert r.status_code == 503, f"Expected 503 got {r.status_code}: {r.text}"
            body = r.text.lower()
            assert "resend" in body or "not configured" in body or "email" in body
        finally:
            requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=TIMEOUT)
