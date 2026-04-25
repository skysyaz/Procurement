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
    """OCR a PDF page-by-page so peak memory stays bounded.

    Rasterising every page upfront at 200 DPI blows past the 512 MB ceiling
    on Render free tier and OOM-kills the worker.  Doing one page at a time
    at 150 DPI keeps peak resident memory under ~50 MB regardless of page
    count.
    """
    try:
        # Imports deferred to avoid import cost when not needed
        import gc
        import pytesseract
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFPageCountError

        # Discover page count without rasterising.
        try:
            n_pages = len(PdfReader(str(path)).pages)
        except Exception:  # noqa: BLE001
            n_pages = 0

        if n_pages <= 0:
            # Fallback: rasterise once (small PDF assumed).
            pages = convert_from_path(str(path), dpi=150)
            try:
                return "\n".join(pytesseract.image_to_string(p) or "" for p in pages).strip()
            finally:
                del pages
                gc.collect()

        chunks: list[str] = []
        for i in range(1, n_pages + 1):
            try:
                # 120 DPI keeps peak per-page bitmap memory ~30 MB while still
                # being legible for tesseract on receipt/quote-grade PDFs.
                imgs = convert_from_path(str(path), dpi=120, first_page=i, last_page=i)
            except PDFPageCountError:
                break
            if imgs:
                chunks.append(pytesseract.image_to_string(imgs[0]) or "")
                imgs[0].close()
                del imgs
                gc.collect()  # explicit GC keeps RSS flat between pages
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
