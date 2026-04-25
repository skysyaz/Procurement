"""LLM-driven structured extraction.
Maps raw OCR text into the per-template JSON schema.

Multi-provider fallback chain (highest priority first):
  1. Google Gemini direct (``GEMINI_API_KEY``) — free tier, ~1500 RPD.
  2. Groq (``GROQ_API_KEY``) — free tier, llama-3.3-70b-versatile.
  3. Emergent Universal Key (``EMERGENT_LLM_KEY``) — paid, budgeted.

Each tier is tried in order; if one fails we move on so a single provider
outage / quota / bad key never blocks extraction. The function returns the
parsed payload AND the name of the provider that actually succeeded so the
Review page can surface "Extracted by: gemini-direct".
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, Tuple

import httpx

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
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


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


async def _call_groq_direct(
    document_type: str, snippet: str, api_key: str
) -> str:
    """Invoke Groq via its OpenAI-compatible REST endpoint.

    Uses ``response_format={"type": "json_object"}`` which constrains the
    model to emit valid JSON. Free tier (~14400 RPD on llama-3.3-70b) is
    plenty for normal procurement workloads.
    """
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt(document_type)},
            {"role": "user", "content": f"OCR TEXT:\n{snippet}"},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Groq response shape: {body!r}") from exc


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


async def _try_provider(
    name: str, raw_caller, document_type: str, snippet: str, api_key: str,
) -> Dict[str, Any] | None:
    """Run one provider and return parsed JSON, or None if it failed.

    Errors are logged but not raised so the caller can fall through to the
    next provider in the chain.  Returns ``None`` on any failure (network,
    auth, rate-limit, parse error).  Stores the last error message on the
    function's ``last_error`` attribute so the caller can surface it.
    """
    _try_provider.last_error = None  # type: ignore[attr-defined]
    try:
        resp = await raw_caller(document_type, snippet, api_key)
    except ExtractionError as exc:
        logger.warning("%s skipped: %s", name, exc)
        _try_provider.last_error = _classify_llm_error(exc)  # type: ignore[attr-defined]
        return None
    except Exception as exc:  # noqa: BLE001
        friendly = _classify_llm_error(exc)
        logger.warning("%s failed for %s: %s", name, document_type, exc)
        _try_provider.last_error = friendly  # type: ignore[attr-defined]
        return None

    parsed = _safe_json_load(resp or "")
    if not isinstance(parsed, dict):
        logger.error("%s returned non-parseable JSON for %s: %s",
                     name, document_type, (resp or "")[:200])
        _try_provider.last_error = (  # type: ignore[attr-defined]
            f"{name}: response could not be parsed as JSON."
        )
        return None
    return parsed


async def extract_structured(
    document_type: str, raw_text: str
) -> Tuple[Dict[str, Any], str]:
    """Run extraction through the provider fallback chain.

    Returns ``(payload, provider_name)`` so callers can record which provider
    actually produced the data (surfaced on the Review page).  ``OTHER`` /
    empty input short-circuits with the empty payload and provider="none".
    """
    if document_type == "OTHER" or not raw_text:
        return _empty_payload(), "none"

    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")

    if not (gemini_key or groq_key or emergent_key):
        logger.warning("No LLM key configured (GEMINI_API_KEY/GROQ_API_KEY/EMERGENT_LLM_KEY)")
        raise ExtractionError(
            "Extraction failed: no LLM API key is configured on the server "
            "(set GEMINI_API_KEY, GROQ_API_KEY, or EMERGENT_LLM_KEY).",
            kind="missing_key",
        )

    # Bound memory: the LLM SDK buffers the full response, so don't feed it
    # an enormous prompt.  12k chars covers virtually every quote/PO/invoice.
    snippet = (raw_text or "")[:12000]

    # Provider fallback chain — tried in order; first successful one wins.
    chain = []
    if gemini_key:
        chain.append(("gemini-direct", _call_gemini_direct, gemini_key))
    if groq_key:
        chain.append(("groq", _call_groq_direct, groq_key))
    if emergent_key:
        chain.append(("emergent", _call_emergent_fallback, emergent_key))

    last_error = "All providers failed."
    parsed: Dict[str, Any] | None = None
    used_provider = ""
    for name, caller, key in chain:
        parsed = await _try_provider(name, caller, document_type, snippet, key)
        if parsed is not None:
            used_provider = name
            logger.info("Extraction succeeded via %s for %s", name, document_type)
            break
        # Capture the last_error from _try_provider for the final message.
        last_error = getattr(_try_provider, "last_error", last_error) or last_error

    if parsed is None:
        raise ExtractionError(last_error)

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

    return parsed, used_provider
