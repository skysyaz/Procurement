"""Gemini-powered PDF text extraction.

Replaces the heavy ``pdf2image + tesseract`` OCR path. Gemini reads PDFs
natively, so we don't rasterise pages into PIL images and don't shell out
to tesseract — peak memory drops from ~400 MB to ~50 MB on Render free
tier, eliminating the OOM-induced ``connection refused`` outage during
bulk uploads.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from emergentintegrations.llm.chat import (
    FileContentWithMimeType, LlmChat, UserMessage,
)

logger = logging.getLogger(__name__)

# gemini-2.5-flash is the recommended balance of cost + accuracy for
# document OCR — handles scans, mixed layouts and tables well, returns
# text quickly and is cheap on the Emergent universal key.
_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = (
    "You are an OCR engine. Read the attached PDF and output ALL textual "
    "content from every page in reading order. "
    "Preserve line breaks between distinct rows/sections. "
    "Do NOT summarise, translate, paraphrase, or add commentary. "
    "Do NOT wrap the output in markdown code fences. "
    "If a page is blank, write '(blank page)' on its own line. "
    "Separate consecutive pages with a blank line."
)


async def extract_text_via_gemini(pdf_path: Path) -> str:
    """Send a local PDF to Gemini and return the extracted text.

    Returns an empty string on any failure so the caller can fall back
    gracefully without the pipeline crashing.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY missing; cannot run Gemini OCR")
        return ""
    if not pdf_path.exists():
        logger.warning("Gemini OCR: file not found %s", pdf_path)
        return ""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ocr-{uuid.uuid4()}",
            system_message=_SYSTEM_PROMPT,
        ).with_model("gemini", _MODEL)

        pdf_file = FileContentWithMimeType(
            file_path=str(pdf_path),
            mime_type="application/pdf",
        )
        resp = await chat.send_message(UserMessage(
            text="Extract all text from this PDF.",
            file_contents=[pdf_file],
        ))
        return (resp or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini OCR failed for %s: %s", pdf_path.name, exc)
        return ""
