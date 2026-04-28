# ProcureFlow — Procurement Document OS (PRD)

## Problem Statement
Extend a procurement web app to support: (1) automated document processing (OCR + AI extraction), (2) manual document creation from templates, (3) PDF generation, (4) multi-user collaboration with roles + audit, (5) bulk processing, (6) email distribution, (7) password reset, (8) admin-editable templates, (9) scalable queue.

## Stack
- **Backend**: FastAPI (Python), MongoDB (Motor), local file storage at `/app/backend/uploads`
- **Queue**: Celery + Redis (supervised); in-process BackgroundTasks fallback when Redis unreachable
- **Frontend**: React 19 + Tailwind + Phosphor (Cabinet Grotesk / IBM Plex Sans)
- **OCR**: `pypdf` (digital) → Tesseract + `pdf2image` (scanned fallback)
- **LLM**: Gemini 2.5 Flash via `google-genai` SDK (GEMINI_API_KEY) + Groq fallback (GROQ_API_KEY)
- **PDF gen**: ReportLab
- **Email**: Resend (graceful 503 when unconfigured) — PDF attachments + password-reset
- **Auth**: JWT (httpOnly cookies + Bearer fallback), bcrypt, email-keyed brute-force lockout, admin seeded on startup

## Personas
- **Admin** — full access; manages users, templates, audit log, queue status
- **Manager** — all documents org-wide; finalizes + emails
- **User** — owns documents they upload/create
- **Viewer** — read-only

## Services
`ocr_service · classification_service · extraction_service · templates · pdf_service · email_service · audit_service · auth_service · storage_service · celery_app`

## API (all under `/api`)
- **Auth**: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/refresh`, `/auth/forgot-password`, `/auth/reset-password`
- **Docs**: `/documents/upload`, `/documents/bulk-upload` (Celery-routed), `/documents/bulk-status`, `/documents/{id}/process`, `/documents` (paginated + regex), `/documents/{id}`, `/documents/{id}/review`, `/documents/create`, `/documents/{id}/file`, `/documents/{id}/pdf`, `/documents/{id}/email`, `DELETE /documents/{id}`
- **Templates**: `/templates`, `/templates/{type}`
- **Admin**: `/admin/users` (list/update role/delete), `/admin/templates` (POST/PUT/DELETE — DB-backed with built-in defaults + reset-to-default), `/admin/queue-status`, `/audit-logs`
- **Dashboard**: `/dashboard/stats`

## Supported Templates (built-in + custom)
PO, PR, DO, QUOTATION, INVOICE — plus any admin-defined custom types (e.g. PACKING_LIST). Schemas stored in `document_templates` MongoDB collection, merged with built-in defaults at startup.

## What's Implemented (2026-04-24)
### Phase 1 — Core pipeline
- OCR → classify → extract → review → PDF generation on 4 templates. Validated on real Quatriz quotation.
- 17/17 initial tests green.

### Phase 2 — Multi-user + production features
- INVOICE template, Tesseract scanned-PDF fallback, server-side pagination + regex search, bulk upload (BackgroundTasks), Resend email for PDF, JWT + 4-role RBAC, audit log.
- 38/38 Phase-2 tests green.

### Phase 3 — Admin power features (2026-04-24)
- **Password reset** flow end-to-end: email token generation → `/reset-password?token=...` landing → password update → login-attempts wipe. Token stored in `password_reset_tokens` with 1h expiry; links logged when Resend unconfigured.
- **Admin template editor** — DB-backed override layer on top of built-in defaults. Admins can create custom types, edit schemas (header fields / item columns / totals / tax rate), and reset built-ins. Schema validator enforces key+label, allowed types, numeric tax_rate.
- **Celery + Redis** queue for bulk processing — both supervised. Bulk upload routes through Celery when Redis reachable; falls back to FastAPI BackgroundTasks otherwise. Admin dashboard shows live queue status (runner, in-flight, pending, failed).
- **19/19 Phase-3 tests** + all Phase-2 regression = **57/57 green**.
- Frontend: Forgot/Reset password pages, Admin Templates page with full CRUD editor, Dashboard queue-status strip, Sidebar "Templates" admin link.

## Prioritized Backlog
- **P1** Store `password_reset_tokens.expires_at` as BSON date + TTL index (auto-expiry)
- **P1** Migrate `@app.on_event` → FastAPI lifespan context
- **P2** Tighten `document_type` regex (reject lowercase raw input)
- **P2** Per-item runner tracking in bulk-upload response
- **P2** Template editor UX: drag-to-reorder fields, JSON preview, duplicate-key warnings
- **P2** Multi-page PDF preview zoom controls
- **P3** Persistent Celery worker loop/Mongo client for throughput
- **P3** Outbound webhooks (on_document_final → Slack/Teams)

## Changelog
- **2026-04-25** **Corporate document layout overhaul** for all 5 manual doc types (QUOTATION, PO, PR, DO, INVOICE):
    - Doc-type-aware "To" block: Quotation→client, Invoice→Bill To, PO→Supplier, PR→Requested By, DO→Deliver To. Falls back across `client_name`/`vendor_name`/`requester_name` so older docs still render.
    - Per-type ref/date rows on right column (PO No+Delivery Date, Request No+Department, DO No+Ref PO, Invoice No+Due Date, etc.).
    - **PR**: 3-cell approval workflow grid (Requested / Reviewed / Approved By) at the bottom.
    - **DO**: Vehicle/Driver/Received-By signature box.
    - **INVOICE**: Payment Details box (Bank, Account, SWIFT) — pulled from header fields or env vars (`BANK_NAME`, `BANK_ACCOUNT`, `BANK_SWIFT`).
    - Authorised signatory now shows **designation** under the name (`issued_by_designation`, fallback `COMPANY_SIGNATORY_TITLE` env).
    - Footer: defensive `_sanitize_env()` strips accidentally-concatenated env vars (e.g. when `COMPANY_REG="988952-X, COMPANY_ADDRESS=Lot G3..."` was pasted on Render). Footer now reads cleanly "Quatriz System Sdn Bhd (988952-X)".
    - Compact title box (40mm × 7mm, 10pt bold, white bg, thin border) — replaces the old chunky 60mm × 18mm gray box.
    - Templates updated with the new fields so the manual create form exposes them: `delivery_address`, `vehicle_no`, `driver_name`, `requester_position`, `reviewer_name/position`, `approver_name/position`, `bank_name/account/swift`, `payment_method`, `issued_by_designation`, etc.
    - Verified by generating PDFs for all 5 types and AI-analyzing each — every check (title placement, addressee block, ref grid, items, totals, type-specific section, signatory, clean footer) ✓ passed.
- **2026-04-25** **Reports status alignment** — fixed bug where filtering Reports by "Approved" returned 0 docs. Frontend dropdown (`Reports.jsx`) now shows friendly labels ("Final / Approved", "Manual Draft", …) but sends canonical codes from `DOC_STATUSES`. Backend `reports_service.py` updated: `COMPLETED_STATUSES = ["FINAL"]`, `PIPELINE_STATUSES` includes `UPLOADED`. PDF report (`report_pdf_service.py`) maps codes → friendly labels too. Verified via curl.
- **2026-04-25** Tightened tesseract memory caps for Render free tier: DPI 120→100 (`ocr_service.py`), `MALLOC_ARENA_MAX=2` (Dockerfile + start.sh), Celery `--max-memory-per-child=250000` (start.sh). Reduces peak worker RSS to keep uvicorn responsive and prevent the "connection refused" OOM kill on bulk uploads.
- **2026-04-25** Tightened mobile/tablet "Original PDF" card on Review.jsx (smaller padding + icon + button + truncation) — removes wasted vertical/horizontal whitespace below the `lg` breakpoint.
- **2026-04-25** *Reverted* Gemini PDF OCR experiment — pypdf+tesseract path retained (user prefers tesseract accuracy on real quotation PDFs).

## Credentials
Seed admin: `syazwan.zulkifli@quatriz.com.my` / `Admin@123` (see `/app/memory/test_credentials.md`).
