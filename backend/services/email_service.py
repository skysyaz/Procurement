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


def send_password_reset_email(to: str, reset_url: str) -> dict:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY missing")
    import resend

    resend.api_key = api_key
    from_email = os.environ.get("RESEND_FROM_EMAIL", "ProcureFlow <onboarding@resend.dev>")

    html = (
        "<div style='font-family:IBM Plex Sans, Arial, sans-serif;font-size:14px;color:#0A0A0B;max-width:480px;margin:0 auto'>"
        "<h2 style='font-family:Cabinet Grotesk, sans-serif;letter-spacing:-0.01em'>Reset your ProcureFlow password</h2>"
        "<p>Someone (hopefully you) asked to reset your password. Click below — the link is valid for 1 hour.</p>"
        f"<p><a href='{reset_url}' style='display:inline-block;background:#0A0A0B;color:#fff;padding:10px 18px;text-decoration:none;border-radius:2px;font-weight:600'>Reset password</a></p>"
        f"<p style='color:#52525B;font-size:12px'>Or copy this link into your browser:<br/><code>{reset_url}</code></p>"
        "<hr style='border:none;border-top:1px solid #E5E7EB;margin:18px 0'/>"
        "<p style='color:#71717A;font-size:12px'>If you didn't request this, you can ignore this email.</p>"
        "</div>"
    )
    return resend.Emails.send({
        "from": from_email, "to": [to],
        "subject": "Reset your ProcureFlow password",
        "html": html,
    })
