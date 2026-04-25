#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Phase 2: redesign the Dashboard with KPI cards + monthly volume chart + spend by type + top vendors (matching the reference image style), build a new Reports page with date/type/status filters + vendor breakdown + filtered docs list + Print button + Download PDF (with Quatriz branding), and ensure all PDFs only stamp the Quatriz logo on MANUAL-source documents (never overwrite branding on uploaded third-party PDFs)."

frontend:
  - task: "Dashboard redesign — KPI cards, monthly chart, spend by type, top vendors"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/Dashboard.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Replaced the old 4-stat-cell Dashboard with a fully responsive layout: 4 KPI cards (Total Documents, Pending Approvals, Pipeline Value, Completed This Month — 2 cols on mobile, 4 on lg+), Runner status row (when admin), 2 charts side-by-side (Monthly Volume bar chart, Spend by Type) stacking on mobile, Recent Activity table + Top Vendors leaderboard, Documents-by-Type breakdown. All cards respect the existing pf-surface design system. Reads from /api/dashboard/summary."

  - task: "Reports page with filters + Print + Download PDF"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/Reports.jsx, frontend/src/App.js, frontend/src/components/Sidebar.jsx, frontend/src/index.css"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "New page at /reports (also added to sidebar nav). Filters: Type, Status, From, To dates (default = last 3 months). 4 KPI cards, Spend-by-Type horizontal bar list, Vendors-by-Spend table, Filtered Documents table. 'Print' button calls window.print() — added @media print stylesheet to index.css that strips the sidebar/buttons and adds a clean print-only header. 'Download PDF' calls /api/reports/pdf with the active filters and triggers a file download. All buttons hidden when printing via print:hidden Tailwind utility + CSS fallback."

  - task: "Review page responsive gap fix (phone-in-desktop-mode)"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/Review.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Root cause: the 2-col split (dark PDF iframe panel + form) used the lg: breakpoint (1024px), so on Chrome desktop-mode at ~980-1023px viewport the iframe column appeared but mobile Chrome can't render inline PDFs → big empty grey area on the left. Fix: bumped the breakpoint to xl: (1280px). At <xl, the layout is single-column with a compact 'Original PDF / Open' bar at the top. Added max-w-[1100px] mx-auto on the form area so it stays readable on the wider single-column. The dark inline iframe preview still works at xl+ where it actually renders correctly. NOT requesting frontend testing — visual fix, will verify on next deploy."

  - task: "Provider-used badge on Review page"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/Review.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added a small blue uppercase badge (data-testid='review-provider-badge') in the Review page header next to the confidence indicator that shows doc.extraction_provider when set ('gemini-direct', 'groq', or 'emergent'). Hidden on small screens (md:inline). Tooltip explains it's the LLM that produced the extraction. Not requesting frontend testing — visual addition only, will verify on the next deployment."

  - task: "Review page extraction-error banner with Retry"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/Review.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added a red banner (data-testid='extraction-error-banner') at the top of the Review page that shows when doc.extraction_error is set OR doc.status === 'FAILED'. Banner displays the human-readable message from the backend (e.g. 'LLM service budget exhausted — top up your Emergent Universal Key and click Retry.') and a 'Retry extraction' button (data-testid='extraction-retry-btn') that POSTs to /api/documents/{id}/process, then re-hydrates the local state from the response. Includes a spinner while retrying and surfaces any retry error inline. NOT requesting frontend testing yet — will ask the user first per protocol."

  - task: "Bulk upload duplicate prevention"
    implemented: true
    working: true
    file: "frontend/src/pages/Upload.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on mobile viewport (412×915). Rapid clicked submit button 5 times within 100ms. Network monitoring confirmed only 1 POST request to /api/documents/bulk-upload was sent. Queued table correctly showed exactly 2 items (not duplicates). Button and file input were properly disabled during upload. The submitting state guard (if (!files.length || submitting) return;) is working correctly."
  
  - task: "Retry button visibility for UPLOADED/FAILED status"
    implemented: true
    working: true
    file: "frontend/src/pages/DocumentList.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Verified retry button (data-testid='retry-{id}') correctly does NOT appear for documents with EXTRACTED, REVIEWED, or FINAL status. Checked 4 documents with EXTRACTED status - none had retry buttons visible. Implementation at lines 136-148 correctly conditionally renders retry button only for UPLOADED or FAILED status."
  
  - task: "Retry button functionality"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/DocumentList.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "testing"
          comment: "Could not test retry button click functionality because all test documents processed successfully to EXTRACTED status. No documents with UPLOADED or FAILED status were available during testing. The retry button implementation appears correct (shows spinner during retry, calls /api/documents/{id}/process endpoint, reloads data after completion), but actual functionality could not be verified in this test run."


  - task: "Auth flow - redirect to login from root"
    implemented: true
    working: true
    file: "frontend/src/App.js, frontend/src/components/Protected.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on 2026-04-25. Opening root URL (/) correctly redirects to /login when not authenticated. Protected route wrapper working as expected."
  
  - task: "Auth flow - login with credentials"
    implemented: true
    working: true
    file: "frontend/src/pages/Login.jsx, frontend/src/lib/auth.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on 2026-04-25. Login with credentials (syazwan.zulkifli@quatriz.com.my / Admin@123) successfully lands on dashboard. User info displayed in sidebar. Login API returns 200 OK."
  
  - task: "Auth flow - session persistence on reload"
    implemented: true
    working: false
    file: "frontend/src/lib/auth.jsx, frontend/src/index.js"
    stuck_count: 1
    priority: "high"
    needs_retesting: false
    status_history:
        - working: false
          agent: "testing"
          comment: "CRITICAL ISSUE: Page reload triggers 2 GET /api/auth/me requests instead of 1. Both requests return 200 OK. Root cause identified: React.StrictMode in index.js (line 8) causes double-mounting of effects in React 18+. The AuthProvider's useEffect runs twice, calling refresh() twice. This is NOT a bug in the retry logic itself (which only retries on network errors/5xx), but a side effect of StrictMode. User stays logged in correctly, but the duplicate request violates the requirement of 'exactly ONE successful GET /api/auth/me on reload'."
  
  - task: "Auth flow - logout functionality"
    implemented: true
    working: true
    file: "frontend/src/components/Sidebar.jsx, frontend/src/lib/auth.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on 2026-04-25. Clicking logout button successfully redirects to /login. Logout API call returns 200 OK. User state cleared correctly."
  
  - task: "Auth flow - no auto-login after logout"
    implemented: true
    working: true
    file: "frontend/src/lib/auth.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on 2026-04-25. After logout, reloading the page stays on /login (does not auto-login). Login form is visible and functional."
  
  - task: "Auth flow - cookie cleanup after logout"
    implemented: true
    working: true
    file: "backend/server.py (logout endpoint)"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested on 2026-04-25. After logout, both access_token and refresh_token cookies are absent. Only Cloudflare cookies (cf_clearance, __cf_bm) remain. Cookie cleanup working correctly."

backend:
  - task: "Reports + Dashboard aggregations and PDF export"
    implemented: true
    working: true
    file: "backend/services/reports_service.py, backend/services/report_pdf_service.py, backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        - working: true
          agent: "main"
          comment: "New endpoints: GET /api/dashboard/summary (KPIs: total_documents, pending_approvals, pipeline_value, completed_value, completed_this_month + monthly_volume[6mo] + spend_by_type + top_vendors[5] + recent[8]). GET /api/reports/summary?from=&to=&type=&status= (kpis, vendors, by_type, monthly buckets, documents list). GET /api/reports/pdf?... returns a print-ready Procurement Report PDF using the same Quatriz brand template. All scoped to user role (admin/manager see all, others see owner-only). Aggregations done in Python after a single Mongo cursor for portability (avoids $expr type-juggling). Smoke-tested: report PDF (64KB) renders correctly with logo, KPI strip, Vendors-by-spend table, and Filtered Documents list — Gemini-Vision confirmed all layout checks pass."

  - task: "Branded PDF only for MANUAL docs (not for uploaded third-party PDFs)"
    implemented: true
    working: true
    file: "backend/services/pdf_service.py, backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        - working: true
          agent: "main"
          comment: "render_document_pdf now takes branded=bool. _render_pdf_or_400 in server.py inspects doc.source — MANUAL → branded=True (full Quatriz template: logo top-left, bordered title top-right, To/Attn block, Ref/SST/Date grid, items table with grid borders, totals stack, terms & conditions box, signature space, centered footer with Quatriz registration + address). AUTO/uploaded → branded=False, neutral 'Extracted Form' rendering with the source filename and a disclaimer that the original branding belongs to the issuing party. This prevents overwriting third-party logos (e.g. Umobile invoices) when the user re-renders the extracted data. Both paths smoke-tested across all 5 doc templates."

  - task: "Quatriz logo + branded header on all generated PDFs"
    implemented: true
    working: true
    file: "backend/services/pdf_service.py, backend/assets/quatriz_logo.png, backend/assets/quatriz_logo_pdf.png, backend/.env, backend/Dockerfile"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Stored full-res logo at backend/assets/quatriz_logo.png and a PDF-optimized 600x400 / 50KB version at backend/assets/quatriz_logo_pdf.png. Added _build_brand_header() to pdf_service: 2-col table with logo + COMPANY_NAME + optional COMPANY_TAGLINE/COMPANY_ADDRESS on the left, document title (PURCHASE ORDER / QUOTATION / etc.) on the right, and a 1pt navy underline separating the band from the body. All 5 doc types (PO, PR, DO, QUOTATION, INVOICE) render correctly with the branded header — smoke-tested locally. Logo gracefully falls back to text if the PNG is missing. Company info is configurable via .env (COMPANY_NAME, COMPANY_TAGLINE, COMPANY_ADDRESS — pipe-separated for address lines). Dockerfile already does COPY backend/ ./ so the assets folder ships automatically. Gemini analysis of the rendered PDF confirms 'professional', 'logo at top left', 'document title at top right', 'clean minimalist design'."

  - task: "Multi-provider LLM fallback (Gemini → Groq → Emergent) with provider tracking"
    implemented: true
    working: true
    file: "backend/services/extraction_service.py, backend/server.py, backend/celery_app.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Refactored extract_structured to walk a provider chain: GEMINI_API_KEY (google-genai SDK, response_mime_type=application/json), then GROQ_API_KEY (httpx POST to https://api.groq.com/openai/v1/chat/completions, llama-3.3-70b-versatile, response_format=json_object), then EMERGENT_LLM_KEY (legacy). Each provider is tried in order; failures (auth, rate-limit, parse error) are logged via _try_provider helper, and we fall through. Final ExtractionError surfaces the LAST tier's friendly classified message via the banner. Function now returns (payload, provider_name) tuple. server.py + celery_app.py updated to receive the tuple and persist extraction_provider on the document. DocumentModel has extraction_provider: Optional[str]. Smoke-tested: (a) real Gemini key returns gemini-direct as provider; (b) bad Gemini + exhausted Emergent walks the chain and returns the budget-exhausted message correctly. Awaiting Groq key from user to test the middle tier explicitly."

  - task: "Switch LLM extraction to free Google Gemini direct (google-genai SDK)"
    implemented: true
    working: true
    file: "backend/services/extraction_service.py, backend/.env, backend/requirements.txt, backend/Dockerfile"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Refactored extract_structured to call Google Gemini directly via the google-genai SDK using GEMINI_API_KEY (free tier, ~1500 requests/day). Uses response_mime_type='application/json' to force valid JSON output. Falls back to Emergent Universal Key only when GEMINI_API_KEY is not set. SDK call wrapped in asyncio.to_thread so it doesn't block the event loop. Added google-genai to Dockerfile (--no-deps to avoid pydantic 2.9 conflict, then explicitly install runtime deps). Smoke-tested locally end-to-end: real key returns proper structured JSON for a sample PO; invalid key correctly raises ExtractionError with friendly 'LLM service rejected the API key' message that surfaces in the Review banner."

  - task: "ExtractionError surfacing on LLM failure"
    implemented: true
    working: "NA"
    file: "backend/services/extraction_service.py, backend/server.py, backend/celery_app.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Refactored extract_structured to raise ExtractionError (with friendly message - detects budget exhausted / rate-limit / timeout / auth) instead of silently returning empty payload. _run_pipeline (server.py) and Celery task (celery_app.py) now catch ExtractionError, persist raw_text + classification + ocr fields, set status=FAILED and store extraction_error string on the document. Successful runs $unset extraction_error. Added extraction_error: Optional[str] field to DocumentModel. Need backend testing: (1) when LLM call raises an exception, document ends up status=FAILED with extraction_error populated; (2) when EMERGENT_LLM_KEY missing, ExtractionError is raised with 'EMERGENT_LLM_KEY is not configured' message; (3) successful retry via POST /api/documents/{id}/process clears the extraction_error field; (4) classification + raw_text are still persisted even on extraction failure."
  - task: "Bulk upload endpoint duplicate prevention"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Backend correctly handled only 1 bulk-upload request despite 5 rapid frontend clicks. Backend logs show: 'POST /api/documents/bulk-upload HTTP/1.1 200 OK' appeared only once. Both documents were successfully uploaded and processed to EXTRACTED status."
  
  - task: "Document processing endpoint for retry"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "testing"
          comment: "Could not test the /api/documents/{id}/process endpoint for retry functionality as no documents remained in UPLOADED or FAILED status during testing."

metadata:
  created_by: "testing_agent"
  version: "1.0"
  test_sequence: 2
  run_ui: true
  test_date: "2026-04-25"
  viewport: "desktop (1920×1080)"
  last_test: "Auth flow sanity check"

test_plan:
  current_focus:
    - "Reports + Dashboard aggregations and PDF export"
    - "Branded PDF only for MANUAL docs (not for uploaded third-party PDFs)"
  stuck_tasks:
    - "Auth flow - session persistence on reload"
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "Phase 2 shipped: (1) PDF service split into branded (MANUAL) and neutral (AUTO/uploaded) paths so third-party docs like Umobile invoices NEVER get the Quatriz logo stamped on them. (2) Branded layout closely matches the user's reference: big logo top-left, bordered QUOTATION/PO box top-right, 2-col To/Ref grid, items table with full grid borders, Sub-total/SST/Grand Total stack with thicker bottom rule, Terms & Conditions box, signature line, centered footer with 'Quatriz System Sdn Bhd (988952-X)' + address. Gemini-Vision validated layout. (3) Dashboard fully redesigned with 4 KPI cards + Monthly chart + Spend by Type + Top Vendors + responsive at every breakpoint. (4) New Reports page at /reports with date/type/status filters, KPI strip, vendor breakdown, filtered docs list, Print button (browser print + clean print stylesheet), and Download PDF button (uses the same branded template). New endpoints: /api/dashboard/summary, /api/reports/summary, /api/reports/pdf — all role-scoped. NOT requesting frontend testing yet — will let user verify on their device first."

agent_communication:
    - agent: "testing"
      message: "Completed testing of bulk upload duplicate prevention and retry button features. Test 1 (duplicate prevention) PASSED completely. Test 2 (retry button) PARTIALLY tested - visibility logic verified but actual retry functionality could not be tested due to all documents processing successfully. Test 3 (cleanup) completed successfully. No console errors detected. Screenshots saved in .screenshots/ directory."
    
    - agent: "testing"
      message: "IMPORTANT NOTE: The retry button functionality (clicking retry and re-processing) could not be fully tested because all uploaded documents immediately processed to EXTRACTED status. To fully test this feature, would need either: (1) a way to upload documents without auto-processing, or (2) artificially create a FAILED document. The implementation code looks correct based on code review."
    
    - agent: "testing"
      message: "AUTH FLOW SANITY CHECK COMPLETED (2026-04-25): Tested auth flow after recent auth context retry logic changes. CRITICAL ISSUE FOUND: Page reload triggers 2 GET /api/auth/me requests instead of 1. Root cause: React.StrictMode in index.js causes double-mounting of effects in React 18+. Both requests succeed (200 OK), so this is not a retry logic bug but a StrictMode side effect. All other auth tests passed: redirect to login, login flow, session persistence, logout, cookie cleanup. Recommend removing StrictMode for production/preview builds or adding ref-based guard to prevent double execution."
