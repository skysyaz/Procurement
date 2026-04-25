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


def _empty_payload() -> Dict[str, Any]:
    return {"header": {}, "items": [], "totals": {}}


class ExtractionError(RuntimeError):
    """Raised when the LLM extraction step fails for a recoverable reason
    (budget exhausted, rate-limited, network blip, parse failure).

    The pipeline catches this to mark the document as FAILED and surface
    a human-readable message in the UI so the user can retry.
    """

    def __init__(self, message: str, *, kind: str = "llm_error") -> None:
        super().__init__(message)
        self.kind = kind


def _classify_llm_error(exc: Exception) -> str:
    """Convert a raw LLM SDK exception into a short, user-facing string.

    Detects the common Emergent Universal Key budget-exhausted case so the
    Review banner can tell the user exactly what happened (instead of a
    silent empty form).
    """
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()
    if "budget has been exceeded" in low or "max budget" in low:
        return "LLM service budget exhausted — top up your Emergent Universal Key and click Retry."
    if "rate limit" in low or "429" in low:
        return "LLM service rate-limited — wait a moment and click Retry."
    if "timeout" in low or "timed out" in low:
        return "LLM service timed out — click Retry to try again."
    if "unauthorized" in low or "invalid api key" in low or "401" in low:
        return "LLM service rejected the API key — check your Emergent Universal Key and click Retry."
    # Generic fallback: keep the first 180 chars so logs stay useful but the
    # banner isn't a wall of text.
    return f"Extraction failed: {msg[:180]}"


def _safe_json_load(raw: str) -> Dict[str, Any] | None:
    """Best-effort JSON extraction from a raw LLM response.

    Tries (in order):
      1. ``json.loads`` on the full cleaned string.
      2. The widest ``{...}`` slice (greedy, dotall) — handles models that
         prepend a "Sure, here is the JSON:" prefix.
      3. A non-greedy first JSON object scan with brace-balance counting,
         which survives nested objects/arrays.
      4. A last-ditch pass that strips trailing commas (``,}`` and ``,]``),
         a very common LLM mistake.

    Returns ``None`` if every attempt fails — the caller falls back to an
    empty payload so the pipeline never raises.
    """
    if not raw:
        return None
    text = _strip_fence(raw)

    # Attempt 1: parse the whole thing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: greedy outermost {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Attempt 3: brace-balanced scan from first '{'
    start = text.find("{")
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Attempt 4: strip trailing commas inside that slice
                        cleaned = re.sub(r",(\s*[\]}])", r"\1", candidate)
                        try:
                            return json.loads(cleaned)
                        except json.JSONDecodeError:
                            break
    return None


async def extract_structured(document_type: str, raw_text: str) -> Dict[str, Any]:
    if document_type == "OTHER" or not raw_text:
        return _empty_payload()

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY missing; raising ExtractionError")
        raise ExtractionError(
            "Extraction failed: EMERGENT_LLM_KEY is not configured on the server.",
            kind="missing_key",
        )

    # Bound memory: the LLM SDK buffers the full response, so don't feed it
    # an enormous prompt.  12k chars covers virtually every quote/PO/invoice.
    snippet = (raw_text or "")[:12000]

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"extract-{uuid.uuid4()}",
            system_message=_system_prompt(document_type),
        ).with_model("gemini", "gemini-2.5-flash")
        resp = await chat.send_message(UserMessage(text=f"OCR TEXT:\n{snippet}"))
    except Exception as exc:  # noqa: BLE001
        # Network blips, rate limits, budget exhaustion, model errors, etc.
        # We surface this to the caller as a typed ExtractionError so the
        # pipeline can mark the document FAILED and show a banner.  The
        # previous behaviour (returning an empty payload silently) left users
        # staring at a blank Review form with no clue why.
        friendly = _classify_llm_error(exc)
        logger.warning("LLM call failed for %s: %s", document_type, exc)
        raise ExtractionError(friendly) from exc

    parsed = _safe_json_load(resp or "")
    if not isinstance(parsed, dict):
        logger.error("LLM returned non-parseable JSON for %s: %s",
                     document_type, (resp or "")[:200])
        raise ExtractionError(
            "Extraction failed: LLM response could not be parsed as JSON. Click Retry to try again.",
            kind="parse_error",
        )

    parsed.setdefault("header", {})
    parsed.setdefault("items", [])
    parsed.setdefault("totals", {})

    # Stabilize quotation identifier placement. LLM occasionally flips the
    # Q-number between quotation_number and reference_number; ensure the
    # primary field is populated so downstream rendering and search work.
    if document_type == "QUOTATION":
        hdr = parsed.get("header") if isinstance(parsed.get("header"), dict) else {}
        if not hdr.get("quotation_number") and hdr.get("reference_number"):
            hdr["quotation_number"] = hdr["reference_number"]
        parsed["header"] = hdr

    return parsed
