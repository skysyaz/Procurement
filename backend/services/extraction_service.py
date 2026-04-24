"""LLM-driven structured extraction.
Maps raw OCR text into the per-template JSON schema.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict

from emergentintegrations.llm.chat import LlmChat, UserMessage

from .templates import get_template

logger = logging.getLogger(__name__)


def _schema_hint(document_type: str) -> str:
    tpl = get_template(document_type)
    if not tpl:
        return ""
    headers = [f["key"] for f in tpl["schema"]["header_fields"]]
    items = [c["key"] for c in tpl["schema"]["item_columns"]]
    totals = [t["key"] for t in tpl["schema"]["totals"]]
    return json.dumps(
        {
            "header": {k: "" for k in headers},
            "items": [{k: "" for k in items}],
            "totals": {k: 0 for k in totals},
        },
        indent=2,
    )


def _system_prompt(document_type: str) -> str:
    schema = _schema_hint(document_type)
    return (
        f"You extract structured data from a {document_type} document. "
        "Return ONLY valid JSON — no prose, no markdown fences — matching this shape exactly:\n"
        f"{schema}\n"
        "Rules:\n"
        "- Use null or empty string when a value is missing.\n"
        "- Numbers must be plain numbers (no currency symbols, no commas).\n"
        "- Dates should be ISO format YYYY-MM-DD when possible; otherwise keep the original.\n"
        "- items is an array; include every line item you can detect.\n"
        "- Do not invent values that are not present in the text."
    )


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


async def extract_structured(document_type: str, raw_text: str) -> Dict[str, Any]:
    if document_type == "OTHER" or not raw_text:
        return {"header": {}, "items": [], "totals": {}}

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY missing; returning empty extraction")
        return {"header": {}, "items": [], "totals": {}}

    chat = LlmChat(
        api_key=api_key,
        session_id=f"extract-{uuid.uuid4()}",
        system_message=_system_prompt(document_type),
    ).with_model("gemini", "gemini-2.5-flash")

    snippet = raw_text[:12000]
    resp = await chat.send_message(UserMessage(text=f"OCR TEXT:\n{snippet}"))
    cleaned = _strip_fence(resp or "")
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to locate the JSON body inside the response
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.error("LLM returned non-JSON: %s", cleaned[:200])
            return {"header": {}, "items": [], "totals": {}}
        parsed = json.loads(match.group(0))

    parsed.setdefault("header", {})
    parsed.setdefault("items", [])
    parsed.setdefault("totals", {})

    # Stabilize quotation identifier placement. LLM occasionally flips the
    # Q-number between quotation_number and reference_number; ensure the
    # primary field is populated so downstream rendering and search work.
    if document_type == "QUOTATION":
        hdr = parsed["header"]
        if not hdr.get("quotation_number") and hdr.get("reference_number"):
            hdr["quotation_number"] = hdr["reference_number"]

    return parsed
