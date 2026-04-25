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

user_problem_statement: "Add defensive UX when LLM extraction fails (budget exhausted, rate limited, parse error): mark document as FAILED with a human-readable extraction_error, show a banner with Retry button on the Review page."

frontend:
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
    - "ExtractionError surfacing on LLM failure"
  stuck_tasks:
    - "Auth flow - session persistence on reload"
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "Implemented defensive UX for LLM extraction failures. Backend: extraction_service raises ExtractionError (with friendly classified message) on LLM exceptions or unparseable JSON instead of silently returning empty payload; pipeline (server.py + celery_app.py) catches it, marks doc FAILED, stores extraction_error string; success path $unset's extraction_error. Added extraction_error field to DocumentModel. Frontend: Red banner on Review page with Retry button. Please backend-test: simulate LLM failure (e.g. by temporarily unsetting EMERGENT_LLM_KEY or mocking) and verify document ends up status=FAILED + has extraction_error populated; verify successful re-process via /api/documents/{id}/process clears extraction_error and sets status=EXTRACTED; verify raw_text + classification still persist on failure."

agent_communication:
    - agent: "testing"
      message: "Completed testing of bulk upload duplicate prevention and retry button features. Test 1 (duplicate prevention) PASSED completely. Test 2 (retry button) PARTIALLY tested - visibility logic verified but actual retry functionality could not be tested due to all documents processing successfully. Test 3 (cleanup) completed successfully. No console errors detected. Screenshots saved in .screenshots/ directory."
    
    - agent: "testing"
      message: "IMPORTANT NOTE: The retry button functionality (clicking retry and re-processing) could not be fully tested because all uploaded documents immediately processed to EXTRACTED status. To fully test this feature, would need either: (1) a way to upload documents without auto-processing, or (2) artificially create a FAILED document. The implementation code looks correct based on code review."
    
    - agent: "testing"
      message: "AUTH FLOW SANITY CHECK COMPLETED (2026-04-25): Tested auth flow after recent auth context retry logic changes. CRITICAL ISSUE FOUND: Page reload triggers 2 GET /api/auth/me requests instead of 1. Root cause: React.StrictMode in index.js causes double-mounting of effects in React 18+. Both requests succeed (200 OK), so this is not a retry logic bug but a StrictMode side effect. All other auth tests passed: redirect to login, login flow, session persistence, logout, cookie cleanup. Recommend removing StrictMode for production/preview builds or adding ref-based guard to prevent double execution."
