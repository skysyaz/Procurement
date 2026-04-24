"""Document classification.
Strategy:
    1. Keyword-based quick match on OCR text.
    2. LLM fallback when keywords are ambiguous.
Returns a tuple (document_type, confidence, method).
"""
from __future__ import annotations

import logging
import os
from typing import Tuple

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

KEYWORDS = {
    "QUOTATION": ["quotation", "quote no", "price validity", "ref no"],
    "PO": ["purchase order", "p.o. no", "po number"],
    "DO": ["delivery order", "delivery note", "received by"],
    "PR": ["purchase request", "purchase requisition", "requester"],
    "INVOICE": ["invoice no", "tax invoice", "invoice"],
}

DOC_TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"]


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


async def classify_by_llm(text: str) -> Tuple[str, float]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or not text:
        return "OTHER", 0.0
    chat = LlmChat(
        api_key=api_key,
        session_id="classify",
        system_message=(
            "You are a document classifier. Given raw OCR text of a business document, "
            "reply with EXACTLY one token from this list: PO, PR, DO, QUOTATION, INVOICE, OTHER. "
            "Choose the best match. No explanation."
        ),
    ).with_model("gemini", "gemini-2.5-flash")

    snippet = text[:4000]
    resp = await chat.send_message(UserMessage(text=snippet))
    answer = (resp or "").strip().upper().split()[0].strip(".,:;")
    if answer not in DOC_TYPES:
        return "OTHER", 0.3
    return answer, 0.85


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
