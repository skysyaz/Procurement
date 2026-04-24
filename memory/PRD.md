# ProcureFlow — Procurement Document Extension (PRD)

## Original Problem Statement
Extend an existing procurement web app to support:
1. **Automated document processing (OCR + AI)** — upload PDF → classify → extract → review/edit → save
2. **Manual document creation** — structured template-based forms for PO, PR, DO, Quotation

Supported types: PO, PR, DO, QUOTATION, INVOICE, OTHER. Must also generate PDF from structured data.

## Stack Chosen (Emergent default, as original Node/TS/Supabase code was not supplied)
- Backend: FastAPI (Python) + MongoDB (Motor) + local file storage under `/app/backend/uploads`
- Frontend: React 19 + Tailwind + Phosphor icons (Cabinet Grotesk + IBM Plex Sans)
- OCR: `pypdf` (digital PDF text extraction)
- LLM: Gemini 2.5 Flash via `emergentintegrations` + Emergent Universal LLM Key
- PDF gen: ReportLab

## Architecture / Services
- `services/ocr_service.py` — text extraction
- `services/classification_service.py` — keyword + LLM fallback
- `services/extraction_service.py` — schema-driven LLM structured extraction
- `services/templates.py` — declarative schemas (header fields, item columns, totals, tax rate) for PO/PR/DO/QUOTATION
- `services/pdf_service.py` — ReportLab renderer

## API Endpoints
- `GET /api/` — health
- `GET /api/dashboard/stats` — totals, by_type, by_status, recent 5
- `GET /api/templates`, `GET /api/templates/{type}`
- `POST /api/documents/upload` — multipart PDF upload
- `POST /api/documents/{id}/process` — OCR → classify → extract
- `GET /api/documents?type=&status=&source=`
- `GET /api/documents/{id}`
- `PUT /api/documents/{id}/review` — save edits + status
- `POST /api/documents/create` — manual create from template
- `GET /api/documents/{id}/file` — stream original PDF
- `GET /api/documents/{id}/pdf` — ReportLab-generated PDF
- `DELETE /api/documents/{id}`

## MongoDB Schema (collection `documents`)
`id, type, status, source, filename, file_url, raw_text, confidence_score, classification_method, extracted_data {header, items, totals}, created_at, updated_at`

## What's Been Implemented (2026-04-24)
- Full backend pipeline — upload, OCR, keyword+LLM classification, schema-based extraction, manual create, PDF generation, CRUD, dashboard stats
- Frontend — Dashboard, Upload & Extract (drag-drop + 4-step pipeline), Document List (type/status/search filters), Review (split PDF viewer + dynamic form), Create Document (dynamic template forms with auto-calculated line items), Templates browser
- Validated end-to-end with user-supplied real Quatriz quotation PDF (QSSB/AFASS/...) — type=QUOTATION, conf=0.75, 2 items, totals 1160/92.8/1252.80
- 17/17 backend integration tests pass (pytest via REACT_APP_BACKEND_URL)

## Prioritized Backlog
- P1: Multi-page PDF preview zoom controls
- P1: Server-side search (regex on header fields) + pagination
- P2: Invoice template schema
- P2: Scanned-PDF OCR path (tesseract + pdf2image) for image-only PDFs
- P2: Role-based auth (JWT) + audit log
- P3: Bulk upload + background job queue
- P3: Email the generated PDF (SendGrid/Resend)
- P3: Template editor UI (edit schema from browser)
