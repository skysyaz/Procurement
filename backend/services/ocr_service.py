"""OCR / text extraction service.
Primary: pypdf text extraction (works on digital PDFs).
Fallback: returns empty string; LLM vision/extraction handles scanned PDFs
downstream by working off whatever text is available plus the filename.
"""
from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        reader = PdfReader(str(path))
        pages_text: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                pages_text.append(page.extract_text() or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to extract text from page %s: %s", i, exc)
        return "\n".join(pages_text).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("PDF text extraction failed: %s", exc)
        return ""
