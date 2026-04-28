"""Document classification.
Strategy:
    1. Keyword-based quick match on OCR text.
    2. LLM fallback when keywords are ambiguous.
       Provider chain: Gemini direct → Groq → (no more fallback)
Returns a tuple (document_type, confidence, method).
"""
from __future__ import annotations

import logging
import os
from typing import Tuple

import httpx

logger = logging.getLogger(__name__)

# Lazy-imported Gemini SDK (optional — won't crash on import if missing)
try:
    from google import genai as _google_genai
    from google.genai import types as _google_genai_types
except Exception:  # noqa: BLE001
    _google_genai = None
    _google_genai_types = None

KEYWORDS = {
    "QUOTATION": ["quotation", "quote no", "price validity", "ref no"],
    "PO": ["purchase order", "p.o. no", "po number"],
    "DO": ["delivery order", "delivery note", "received by"],
    "PR": ["purchase request", "purchase requisition", "requester"],
    "INVOICE": ["invoice no", "tax invoice", "invoice"],
}

DOC_TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"]

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_SYSTEM_MSG = (
    "You are a document classifier. Given raw OCR text of a business document, "
    "reply with EXACTLY one token from this list: PO, PR, DO, QUOTATION, INVOICE, OTHER. "
    "Choose the best match. No explanation."
)


def classify_by_keywords(text: str) -> Tuple[str, float]:
    if not text:
        return "OTHER", 0.0
    lower = text.lower()
    scores: dict[str, int] = {dt: 0 for dt in KEYWORDS}
    for dt, words in KEYWORDS.items():
        for w in words:
            if w in lower:
                scores[dt] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "OTHER", 0.0
    total = sum(scores.values())
    return best, round(scores[best] / max(total, 1), 2)


async def _classify_gemini(text: str, api_key: str) -> Tuple[str, float] | None:
    """Classify via Google Gemini direct SDK."""
    if _google_genai is None or _google_genai_types is None:
        logger.warning("google-genai SDK not installed; skipping Gemini classification")
        return None
    try:
        import asyncio

        def _invoke() -> str:
            client = _google_genai.Client(api_key=api_key)
            cfg = _google_genai_types.GenerateContentConfig(
                system_instruction=_SYSTEM_MSG,
                temperature=0.0,
                max_output_tokens=16,
            )
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[text[:4000]],
                config=cfg,
            )
            return getattr(resp, "text", "") or ""

        raw = await asyncio.to_thread(_invoke)
        answer = (raw or "").strip().upper().split()[0].strip(".,:;")
        if answer not in DOC_TYPES:
            return "OTHER", 0.3
        return answer, 0.85
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini classification failed: %s", exc)
        return None


async def _classify_groq(text: str, api_key: str) -> Tuple[str, float] | None:
    """Classify via Groq OpenAI-compatible endpoint."""
    try:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": text[:4000]},
            ],
            "temperature": 0.0,
            "max_tokens": 16,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        raw = body["choices"][0]["message"]["content"] or ""
        answer = (raw or "").strip().upper().split()[0].strip(".,:;")
        if answer not in DOC_TYPES:
            return "OTHER", 0.3
        return answer, 0.85
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq classification failed: %s", exc)
        return None


async def classify_by_llm(text: str) -> Tuple[str, float]:
    """Try Gemini → Groq in order; return first successful result."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    if not text or not (gemini_key or groq_key):
        return "OTHER", 0.0

    if gemini_key:
        result = await _classify_gemini(text, gemini_key)
        if result is not None:
            return result

    if groq_key:
        result = await _classify_groq(text, groq_key)
        if result is not None:
            return result

    return "OTHER", 0.0


async def classify(text: str) -> Tuple[str, float, str]:
    dt, conf = classify_by_keywords(text)
    if conf >= 0.4:
        return dt, conf, "keyword"
    try:
        dt2, conf2 = await classify_by_llm(text)
        return dt2, conf2, "llm"
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM classification failed: %s", exc)
        return dt, conf or 0.1, "keyword-fallback"
