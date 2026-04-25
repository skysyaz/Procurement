"""LLM-driven structured extraction.
Maps raw OCR text into the per-template JSON schema.

Uses Google Gemini directly via the official ``google-genai`` SDK (free tier,
generous quotas) when ``GEMINI_API_KEY`` is configured.  Falls back to the
Emergent Universal Key (paid, budgeted) when only ``EMERGENT_LLM_KEY`` is
available — that path remains so existing deployments keep working.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict

from .templates import get_template

logger = logging.getLogger(__name__)

# Lazy-imported SDKs (don't blow up on import if either is missing).
try:  # google-genai is the preferred path (free tier).
    from google import genai as _google_genai
    from google.genai import types as _google_genai_types
except Exception:  # noqa: BLE001
    _google_genai = None
    _google_genai_types = None

try:  # Emergent universal key is the fallback path.
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except Exception:  # noqa: BLE001
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


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
        return "LLM service budget exhausted — top up your API key (or switch to a free Gemini key) and click Retry."
    if "quota" in low and ("exceed" in low or "exhaust" in low):
        return "LLM free-tier quota reached for the day — wait a bit and click Retry, or switch keys."
    if "rate limit" in low or "429" in low or "resource_exhausted" in low:
        return "LLM service rate-limited — wait a moment and click Retry."
    if "timeout" in low or "timed out" in low:
        return "LLM service timed out — click Retry to try again."
    if "unauthorized" in low or "invalid api key" in low or "api_key_invalid" in low or "401" in low:
        return "LLM service rejected the API key — check GEMINI_API_KEY (or EMERGENT_LLM_KEY) and click Retry."
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


async def _call_gemini_direct(
    document_type: str, snippet: str, api_key: str
) -> str:
    """Invoke Gemini via the official google-genai SDK.

    Uses ``response_mime_type='application/json'`` which constrains the model
    to emit valid JSON — eliminates the trailing-comma / fence parsing dance
    we needed for unconstrained chat output.
    Runs the sync SDK call inside a thread so we don't block the event loop.
    """
    if _google_genai is None or _google_genai_types is None:
        raise ExtractionError(
            "Extraction failed: google-genai SDK is not installed on the server.",
            kind="missing_sdk",
        )

    def _invoke() -> str:
        client = _google_genai.Client(api_key=api_key)
        cfg = _google_genai_types.GenerateContentConfig(
            system_instruction=_system_prompt(document_type),
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=4096,
        )
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[f"OCR TEXT:\n{snippet}"],
            config=cfg,
        )
        return getattr(resp, "text", "") or ""

    return await asyncio.to_thread(_invoke)


async def _call_emergent_fallback(
    document_type: str, snippet: str, api_key: str
) -> str:
    """Invoke the Emergent Universal Key path (legacy/fallback)."""
    if LlmChat is None or UserMessage is None:
        raise ExtractionError(
            "Extraction failed: emergentintegrations SDK is not installed.",
            kind="missing_sdk",
        )
    chat = LlmChat(
        api_key=api_key,
        session_id=f"extract-{uuid.uuid4()}",
        system_message=_system_prompt(document_type),
    ).with_model("gemini", GEMINI_MODEL)
    return await chat.send_message(UserMessage(text=f"OCR TEXT:\n{snippet}"))


async def extract_structured(document_type: str, raw_text: str) -> Dict[str, Any]:
    if document_type == "OTHER" or not raw_text:
        return _empty_payload()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")

    if not gemini_key and not emergent_key:
        logger.warning("No LLM key configured (GEMINI_API_KEY/EMERGENT_LLM_KEY)")
        raise ExtractionError(
            "Extraction failed: no LLM API key is configured on the server "
            "(set GEMINI_API_KEY for the free Gemini tier, or EMERGENT_LLM_KEY).",
            kind="missing_key",
        )

    # Bound memory: the LLM SDK buffers the full response, so don't feed it
    # an enormous prompt.  12k chars covers virtually every quote/PO/invoice.
    snippet = (raw_text or "")[:12000]
    provider = "gemini-direct" if gemini_key else "emergent"

    try:
        if gemini_key:
            resp = await _call_gemini_direct(document_type, snippet, gemini_key)
        else:
            resp = await _call_emergent_fallback(document_type, snippet, emergent_key)
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        # Network blips, rate limits, budget exhaustion, model errors, etc.
        # Surface as ExtractionError so the pipeline marks doc FAILED and
        # the Review banner can tell the user what went wrong.
        friendly = _classify_llm_error(exc)
        logger.warning("LLM call (%s) failed for %s: %s", provider, document_type, exc)
        raise ExtractionError(friendly) from exc

    parsed = _safe_json_load(resp or "")
    if not isinstance(parsed, dict):
        logger.error(
            "LLM (%s) returned non-parseable JSON for %s: %s",
            provider, document_type, (resp or "")[:200],
        )
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
