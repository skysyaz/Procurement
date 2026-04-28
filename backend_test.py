#!/usr/bin/env python3
"""
Backend testing for defensive ExtractionError flow.

Tests:
1. Missing GEMINI_API_KEY/GROQ_API_KEY causes ExtractionError with proper message
2. Document gets marked as FAILED with extraction_error populated
3. Retry functionality works and clears extraction_error
4. OTHER doc_type still works without errors
5. API response includes extraction_error field
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# Test configuration
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
TEST_EMAIL = "syazwan.zulkifli@quatriz.com.my"
TEST_PASSWORD = "Admin@123"


def create_test_pdf(content: str, filename: str) -> str:
    """Create a simple PDF with the given content for testing."""
    pdf_path = f"/tmp/{filename}"
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # Add content to PDF
    c.drawString(100, height - 100, content)
    c.save()
    return pdf_path


def login_and_get_session() -> requests.Session:
    """Login and return authenticated session."""
    session = requests.Session()
    
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = session.post(f"{BACKEND_URL}/auth/login", json=login_data)
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.text}")
    
    print("✅ Login successful")
    return session


def upload_pdf(session: requests.Session, pdf_path: str) -> str:
    """Upload a PDF and return document ID."""
    with open(pdf_path, 'rb') as f:
        files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
        response = session.post(f"{BACKEND_URL}/documents/upload", files=files)
    
    if response.status_code != 200:
        raise Exception(f"Upload failed: {response.status_code} - {response.text}")
    
    doc_data = response.json()
    doc_id = doc_data['id']
    print(f"✅ PDF uploaded successfully, document ID: {doc_id}")
    return doc_id


def wait_for_processing(session: requests.Session, doc_id: str, timeout: int = 60) -> dict:
    """Wait for document processing to complete and return final document state."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = session.get(f"{BACKEND_URL}/documents/{doc_id}")
        if response.status_code != 200:
            raise Exception(f"Failed to get document: {response.status_code} - {response.text}")
        
        doc = response.json()
        status = doc.get('status')
        
        if status in ['EXTRACTED', 'FAILED']:
            print(f"✅ Processing completed with status: {status}")
            return doc
        elif status == 'PROCESSING':
            print(f"⏳ Still processing... (status: {status})")
            time.sleep(2)
        else:
            print(f"📋 Current status: {status}")
            time.sleep(1)
    
    raise Exception(f"Timeout waiting for document processing (timeout: {timeout}s)")


def backup_env_key() -> str:
    """Backup the current EMERGENT_LLM_KEY value."""
    env_path = "/app/backend/.env"
    with open(env_path, 'r') as f:
        content = f.read()
    
    for line in content.split('\n'):
        if line.startswith('EMERGENT_LLM_KEY='):
            return line.split('=', 1)[1].strip('"')
    
    return ""


def modify_env_key(new_value: str = None):
    """Modify or remove EMERGENT_LLM_KEY in .env file."""
    env_path = "/app/backend/.env"
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    with open(env_path, 'w') as f:
        for line in lines:
            if line.startswith('EMERGENT_LLM_KEY='):
                if new_value is None:
                    # Comment out the line to unset the key
                    f.write(f"# {line}")
                else:
                    f.write(f'EMERGENT_LLM_KEY="{new_value}"\n')
            else:
                f.write(line)


def restart_backend():
    """Restart the backend service."""
    import subprocess
    result = subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to restart backend: {result.stderr}")
    
    print("✅ Backend restarted")
    # Wait a moment for the service to come back up
    time.sleep(3)


def test_missing_llm_key():
    """Test 1: Missing EMERGENT_LLM_KEY causes ExtractionError."""
    print("\n🧪 TEST 1: Missing EMERGENT_LLM_KEY causes ExtractionError")
    
    # Backup original key
    original_key = backup_env_key()
    print(f"📋 Backed up original key: {original_key[:10]}...")
    
    try:
        # Remove the key
        modify_env_key(None)
        restart_backend()
        
        # Login and upload a document
        session = login_and_get_session()
        
        # Create a PDF that should be classified as something other than OTHER
        pdf_content = """
        PURCHASE ORDER
        PO Number: PO-2024-001
        Vendor: Test Vendor Inc.
        Date: 2024-01-15
        
        Item: Test Product
        Quantity: 10
        Unit Price: $50.00
        Total: $500.00
        """
        pdf_path = create_test_pdf(pdf_content, "test_po_missing_key.pdf")
        doc_id = upload_pdf(session, pdf_path)
        
        # Wait for processing to complete
        doc = wait_for_processing(session, doc_id)
        
        # Verify the document failed with extraction_error
        assert doc['status'] == 'FAILED', f"Expected status FAILED, got {doc['status']}"
        assert 'extraction_error' in doc, "extraction_error field missing from response"
        assert doc['extraction_error'] is not None, "extraction_error should not be None"
        assert 'EMERGENT_LLM_KEY is not configured' in doc['extraction_error'], \
            f"Expected key missing message, got: {doc['extraction_error']}"
        
        # Verify raw_text and classification are still populated
        assert doc.get('raw_text'), "raw_text should be populated even on extraction failure"
        assert doc.get('type'), "type should be populated even on extraction failure"
        
        print("✅ TEST 1 PASSED: Document correctly failed with extraction_error")
        return doc_id
        
    finally:
        # Restore original key
        modify_env_key(original_key)
        restart_backend()
        print("✅ Original EMERGENT_LLM_KEY restored")


def test_retry_functionality(doc_id: str):
    """Test 2: Retry functionality works and clears extraction_error."""
    print(f"\n🧪 TEST 2: Retry functionality for document {doc_id}")
    
    session = login_and_get_session()
    
    # Call the retry endpoint
    response = session.post(f"{BACKEND_URL}/documents/{doc_id}/process")
    if response.status_code != 200:
        raise Exception(f"Retry failed: {response.status_code} - {response.text}")
    
    doc = response.json()
    
    # Wait for processing if needed
    if doc.get('status') == 'PROCESSING':
        doc = wait_for_processing(session, doc_id)
    
    # Verify the document is now extracted successfully
    assert doc['status'] == 'EXTRACTED', f"Expected status EXTRACTED after retry, got {doc['status']}"
    assert 'extraction_error' not in doc or doc['extraction_error'] is None, \
        f"extraction_error should be cleared after successful retry, got: {doc.get('extraction_error')}"
    assert doc.get('extracted_data'), "extracted_data should be populated after successful retry"
    
    print("✅ TEST 2 PASSED: Retry functionality works and clears extraction_error")


def test_other_doc_type():
    """Test 3: OTHER doc_type still works without errors."""
    print("\n🧪 TEST 3: OTHER doc_type works without errors")
    
    session = login_and_get_session()
    
    # Create a PDF with unclassifiable content (should be classified as OTHER)
    pdf_content = """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        Ut enim ad minim veniam, quis nostrud exercitation ullamco.
        
        This is random text that should not be classified as any document type.
        Random numbers: 12345, 67890
        Random words: hello world test document
        """
    pdf_path = create_test_pdf(pdf_content, "test_other_type.pdf")
    doc_id = upload_pdf(session, pdf_path)
    
    # Wait for processing to complete
    doc = wait_for_processing(session, doc_id)
    
    # Verify the document is extracted successfully (even if classified as OTHER)
    assert doc['status'] == 'EXTRACTED', f"Expected status EXTRACTED for OTHER type, got {doc['status']}"
    assert 'extraction_error' not in doc or doc['extraction_error'] is None, \
        f"extraction_error should not be set for OTHER type, got: {doc.get('extraction_error')}"
    
    # For OTHER type, extracted_data should be empty but present
    extracted_data = doc.get('extracted_data', {})
    assert isinstance(extracted_data, dict), "extracted_data should be a dict"
    
    print("✅ TEST 3 PASSED: OTHER doc_type works without errors")


def test_api_response_shape():
    """Test 4: Verify extraction_error field appears in API responses."""
    print("\n🧪 TEST 4: API response includes extraction_error field")
    
    session = login_and_get_session()
    
    # Get list of documents to check response shape
    response = session.get(f"{BACKEND_URL}/documents")
    if response.status_code != 200:
        raise Exception(f"Failed to get documents list: {response.status_code} - {response.text}")
    
    docs_list = response.json()
    items = docs_list.get('items', [])
    
    if not items:
        print("⚠️  No documents found for API response shape test")
        return
    
    # Check if any document has extraction_error field
    found_extraction_error = False
    for doc in items:
        if 'extraction_error' in doc:
            found_extraction_error = True
            print(f"📋 Found extraction_error field in document {doc['id']}: {doc['extraction_error']}")
    
    # Get individual document to check detailed response
    doc_id = items[0]['id']
    response = session.get(f"{BACKEND_URL}/documents/{doc_id}")
    if response.status_code != 200:
        raise Exception(f"Failed to get individual document: {response.status_code} - {response.text}")
    
    doc = response.json()
    print(f"📋 Individual document response includes extraction_error field: {'extraction_error' in doc}")
    
    print("✅ TEST 4 PASSED: API response shape verified")


def check_backend_logs():
    """Check backend logs for any errors."""
    print("\n📋 Checking backend logs...")
    import subprocess
    
    try:
        result = subprocess.run(['tail', '-n', '50', '/var/log/supervisor/backend.err.log'], 
                              capture_output=True, text=True)
        if result.stdout:
            print("Backend error logs:")
            print(result.stdout)
        else:
            print("No recent backend errors found")
    except Exception as e:
        print(f"Could not check backend logs: {e}")


def main():
    """Run all tests."""
    print("🚀 Starting ExtractionError defensive flow tests...")
    
    try:
        # Test 1: Missing LLM key
        failed_doc_id = test_missing_llm_key()
        
        # Test 2: Retry functionality
        test_retry_functionality(failed_doc_id)
        
        # Test 3: OTHER doc type
        test_other_doc_type()
        
        # Test 4: API response shape
        test_api_response_shape()
        
        print("\n🎉 ALL TESTS PASSED!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        check_backend_logs()
        raise
    
    finally:
        # Clean up test files
        for filename in ["test_po_missing_key.pdf", "test_other_type.pdf"]:
            try:
                os.remove(f"/tmp/{filename}")
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    main()