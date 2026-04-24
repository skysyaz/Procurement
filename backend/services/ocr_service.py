"""OCR service with digital-PDF fast-path and Tesseract fallback for scans."""
from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

_MIN_CHARS_FOR_DIGITAL = 40  # below this, assume scanned


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


def _extract_ocr(path: Path) -> str:
    try:
        # Imports deferred to avoid import cost when not needed
        import pytesseract
        from pdf2image import convert_from_path

        pages = convert_from_path(str(path), dpi=200)
        chunks = []
        for img in pages:
            chunks.append(pytesseract.image_to_string(img) or "")
        return "\n".join(chunks).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract OCR failed: %s", exc)
        return ""


def extract_text_from_pdf(file_path: str | Path) -> tuple[str, str]:
    """Return (text, method) where method ∈ {'digital', 'ocr', 'empty'}."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    digital = _extract_digital(path)
    if len(digital) >= _MIN_CHARS_FOR_DIGITAL:
        return digital, "digital"

    ocr = _extract_ocr(path)
    if ocr:
        return ocr, "ocr"

    return digital, "empty" if not digital else "digital"
