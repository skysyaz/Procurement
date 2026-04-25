"""PDF text extraction.

Strategy:
    1. Fast digital-text path via ``pypdf`` — free, no LLM call, works for
       any born-digital PDF (90 %+ of real-world quotes / invoices / POs).
    2. Gemini PDF fallback for scanned PDFs (replaces the old
       pdf2image + tesseract path that OOM-killed the Render free tier).
"""
from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

from .gemini_pdf_service import extract_text_via_gemini

logger = logging.getLogger(__name__)

_MIN_CHARS_FOR_DIGITAL = 40  # below this, treat as scanned and send to Gemini


def _extract_digital(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                continue
        return "\n".join(pages).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pypdf failed: %s", exc)
        return ""


async def extract_text_from_pdf(file_path: str | Path) -> tuple[str, str]:
    """Return (text, method) where method ∈ {'digital', 'gemini', 'empty'}."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    digital = _extract_digital(path)
    if len(digital) >= _MIN_CHARS_FOR_DIGITAL:
        return digital, "digital"

    gemini_text = await extract_text_via_gemini(path)
    if gemini_text:
        return gemini_text, "gemini"

    return digital, "digital" if digital else "empty"
