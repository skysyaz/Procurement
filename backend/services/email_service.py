"""Resend-backed email service. Gracefully no-ops when unconfigured."""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def send_pdf_email(
    to: str,
    subject: str,
    message: str,
    pdf_bytes: bytes,
    filename: str,
    cc: Optional[str] = None,
) -> dict:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY missing. Add it in /app/backend/.env and restart backend."
        )

    import resend

    resend.api_key = api_key
    from_email = os.environ.get("RESEND_FROM_EMAIL", "ProcureFlow <onboarding@resend.dev>")

    params: dict = {
        "from": from_email,
        "to": [to],
        "subject": subject or "Document from ProcureFlow",
        "html": (
            f"<div style='font-family:IBM Plex Sans, Arial, sans-serif;font-size:14px;color:#0A0A0B'>"
            f"{(message or '').replace(chr(10), '<br/>')}"
            f"<hr style='border:none;border-top:1px solid #E5E7EB;margin:18px 0'/>"
            f"<div style='color:#71717A;font-size:12px'>Sent via ProcureFlow</div>"
            f"</div>"
        ),
        "attachments": [
            {
                "filename": filename,
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ],
    }
    if cc:
        params["cc"] = [cc]

    logger.info("Sending email via Resend to %s", to)
    return resend.Emails.send(params)
