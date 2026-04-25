"""Print-ready PDF for the Reports page (branded with Quatriz header).

Structurally similar to ``pdf_service._render_branded`` but the body is a
financial summary: KPI strip + vendor breakdown table + filtered documents
list. We reuse the same brand colours, footer, and font scale so all output
PDFs feel like part of one family.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .pdf_service import (
    LOGO_PATH, COMPANY_NAME, COMPANY_REG, COMPANY_ADDRESS,
    LEFT, RIGHT, USABLE_W, PAGE_W, INK, MUTED,
    _branded_top_band, _styles, _fmt_num,
)


def _kpi_strip(kpis: Dict[str, Any], st) -> Table:
    """Four-cell KPI band: doc count, grand total, types, statuses."""
    by_type = kpis.get("by_type_count") or {}
    by_status = kpis.get("by_status_count") or {}
    type_summary = ", ".join(f"{k}: {v}" for k, v in by_type.items()) or "—"
    status_summary = ", ".join(f"{k}: {v}" for k, v in by_status.items()) or "—"

    cells = [
        ["DOCUMENTS", str(kpis.get("doc_count", 0))],
        ["GRAND TOTAL (RM)", _fmt_num(kpis.get("grand_total", 0))],
        ["BY TYPE", type_summary],
        ["BY STATUS", status_summary],
    ]
    rows = [
        [
            Paragraph(label, st["label"]),
            Paragraph(f"<b>{value}</b>", st["value_bold"]),
        ]
        for label, value in cells
    ]
    tbl = Table(rows, colWidths=[40 * mm, USABLE_W - 40 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, INK),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, INK),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
            ]
        )
    )
    return tbl


def _vendors_table(vendors: List[Dict[str, Any]], st) -> Table:
    head = ["#", "VENDOR / COUNTER-PARTY", "DOCS", "SPEND (RM)"]
    body: List[List[Any]] = []
    for i, v in enumerate(vendors[:25], start=1):
        body.append([
            str(i),
            Paragraph(v["name"], st["value"]),
            str(v.get("count", 0)),
            _fmt_num(v.get("spend", 0)),
        ])
    if not body:
        body.append(["", Paragraph("<i>No vendor activity in this period.</i>", st["small"]), "", ""])

    col_widths = [10 * mm, USABLE_W - 60 * mm, 18 * mm, 32 * mm]
    tbl = Table([head] + body, repeatRows=1, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, INK),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F4")),
            ]
        )
    )
    return tbl


def _docs_table(docs: List[Dict[str, Any]], st) -> Table:
    head = ["DATE", "TYPE", "REF", "VENDOR", "STATUS", "AMOUNT (RM)"]
    body: List[List[Any]] = []
    for d in docs[:80]:
        # Format date short
        created = d.get("created_at") or ""
        date_label = created[:10] if created else ""
        body.append([
            date_label,
            d.get("type") or "",
            Paragraph(d.get("reference") or "—", st["small"]),
            Paragraph(d.get("vendor") or "—", st["small"]),
            d.get("status") or "",
            _fmt_num(d.get("amount", 0)),
        ])
    if not body:
        body.append(["", "", Paragraph("<i>No documents match the filters.</i>", st["small"]), "", "", ""])

    col_widths = [22 * mm, 22 * mm, 32 * mm, USABLE_W - (22 + 22 + 32 + 22 + 26) * mm, 22 * mm, 26 * mm]
    tbl = Table([head] + body, repeatRows=1, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, INK),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F4")),
            ]
        )
    )
    return tbl


def _draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(INK)
    line1 = f"{COMPANY_NAME} ({COMPANY_REG})" if COMPANY_REG else COMPANY_NAME
    canvas.drawCentredString(PAGE_W / 2, 14 * mm, line1)
    if COMPANY_ADDRESS:
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        for i, line in enumerate(COMPANY_ADDRESS.split("|")):
            line = line.strip()
            if not line:
                continue
            canvas.drawCentredString(PAGE_W / 2, (10 - i * 3.5) * mm, line)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - RIGHT, 297 * mm - 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_report_pdf(summary: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=14 * mm, bottomMargin=20 * mm,
        title=f"Procurement Report - {COMPANY_NAME}",
    )
    st = _styles()
    story: List[Any] = []
    story.append(_branded_top_band("PROCUREMENT REPORT", st))
    story.append(Spacer(1, 6))

    # Filters line
    f = summary.get("filters") or {}
    f_line = (
        f"Type: <b>{f.get('type', 'ALL')}</b>  &nbsp;&nbsp;"
        f"Status: <b>{f.get('status', 'ALL')}</b>  &nbsp;&nbsp;"
        f"From: <b>{f.get('from') or '—'}</b>  &nbsp;&nbsp;"
        f"To: <b>{f.get('to') or '—'}</b>  &nbsp;&nbsp;"
        f"Generated: <b>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</b>"
    )
    story.append(Paragraph(f_line, st["small"]))
    story.append(Spacer(1, 10))

    story.append(_kpi_strip(summary.get("kpis") or {}, st))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>VENDORS BY SPEND</b>", st["value_bold"]))
    story.append(Spacer(1, 4))
    story.append(_vendors_table(summary.get("vendors") or [], st))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>FILTERED DOCUMENTS</b>", st["value_bold"]))
    story.append(Spacer(1, 4))
    story.append(_docs_table(summary.get("documents") or [], st))

    pdf.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()
