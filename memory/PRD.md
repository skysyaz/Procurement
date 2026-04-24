# ProcureFlow — Procurement Document OS (PRD)

## Problem Statement
Extend a procurement web app to support: (1) automated document processing (OCR + AI extraction), (2) manual document creation from templates, (3) PDF generation, (4) multi-user collaboration with roles + audit, (5) bulk processing, (6) email distribution.

## Stack
- **Backend**: FastAPI (Python), MongoDB (Motor), local file storage at `/app/backend/uploads`
- **Frontend**: React 19 + Tailwind + Phosphor (Cabinet Grotesk / IBM Plex Sans)
- **OCR**: `pypdf` (digital) → Tesseract + `pdf2image` (scanned fallback)
- **LLM**: Gemini 2.5 Flash via `emergentintegrations` + Emergent Universal LLM Key
- **PDF gen**: ReportLab
- **Email**: Resend (graceful 503 when `RESEND_API_KEY` unset)
- **Auth**: JWT (httpOnly cookies + Bearer fallback), bcrypt hashing, 5-failure brute-force lockout (keyed by email across pods)

## Personas
- **Admin** — full access; manages users, views audit log.
- **Manager** — all documents org-wide; finalizes, emails.
- **User** — owns documents they upload/create.
- **Viewer** — read-only.

## Core Modules / Services
- `services/ocr_service.py` · `classification_service.py` · `extraction_service.py` · `templates.py` · `pdf_service.py` · `email_service.py` · `audit_service.py` · `auth_service.py`

## API (all under `/api`)
**Auth**: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/refresh`
**Docs**: `/documents/upload`, `/documents/bulk-upload`, `/documents/bulk-status`, `/documents/{id}/process`, `/documents` (paginated + regex search), `/documents/{id}`, `/documents/{id}/review`, `/documents/create`, `/documents/{id}/file`, `/documents/{id}/pdf`, `/documents/{id}/email`, `DELETE /documents/{id}`
**Templates**: `/templates`, `/templates/{type}`
**Dashboard**: `/dashboard/stats`
**Admin**: `/admin/users`, `/admin/users/{id}/role`, `DELETE /admin/users/{id}`, `/audit-logs`

## Templates Supported
PO, PR, DO, QUOTATION, INVOICE

## What's Implemented (2026-04-24)
### Phase 1
- Full OCR → classify → extract → review → PDF generation pipeline on 4 templates
- Validated live on a real Quatriz quotation PDF
- 17/17 Phase-1 backend tests green

### Phase 2
- INVOICE template
- Tesseract scanned-PDF fallback (digital-first, OCR fallback)
- Server-side pagination + regex search across filename + 9 header fields
- Bulk upload (≤20 PDFs) with FastAPI BackgroundTasks + polling status endpoint
- Resend-powered email with styled HTML + PDF attachment (503 when unconfigured)
- JWT auth: login/register/me/logout/refresh, bcrypt, httpOnly cookies + Bearer fallback
- Brute-force lockout (email-keyed, works behind multi-pod ingress) — verified via curl
- 4-role RBAC enforced on every write endpoint + ownership scoping on reads for user/viewer
- Audit log collection with Admin-only browse UI + filter
- Admin Users page (role change + delete, self-demote/delete guarded)
- **38/38 Phase-2 backend tests green**
- Frontend: Login/Register pages, AuthContext, ProtectedRoute, user menu, admin navigation, bulk upload UI, Email dialog, server-side pagination controls

## Backlog (Prioritized)
- **P1** Store `login_attempts.locked_until` as native BSON date + TTL auto-expiry
- **P1** Lifespan context manager instead of `@app.on_event`
- **P2** Password reset flow (email token) — hook into Resend
- **P2** Template editor UI (edit schemas from browser)
- **P2** Multi-page PDF preview zoom controls
- **P3** Replace in-process BackgroundTasks with Celery/Redis when scale demands
- **P3** Signed URLs for generated PDFs (for email CTAs)
- **P3** Outbound webhooks (on_document_final → Slack/Teams)

## Credentials
Seed admin: `syazwan.zulkifli@quatriz.com.my` / `Admin@123` (see `/app/memory/test_credentials.md`).
