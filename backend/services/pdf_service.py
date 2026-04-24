"""PDF generation for structured documents using ReportLab."""
from __future__ import annotations

import io
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .templates import get_template


def _val(data: Dict[str, Any], key: str) -> str:
    v = data.get(key)
    if v is None or v == "":
        return ""
    return str(v)


def _fmt_num(v: Any) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def render_document_pdf(document_type: str, data: Dict[str, Any]) -> bytes:
    tpl = get_template(document_type)
    if not tpl:
        raise ValueError(f"Unknown document type: {document_type}")

    header = data.get("header", {}) or {}
    items = data.get("items", []) or []
    totals = data.get("totals", {}) or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=20, leading=24,
        textColor=colors.HexColor("#0A0A0B"), alignment=1, spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"], fontSize=8, leading=10,
        textColor=colors.HexColor("#52525B"),
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"], fontSize=10, leading=13,
        textColor=colors.HexColor("#0A0A0B"),
    )

    story = []
    story.append(Paragraph(tpl["label"].upper(), title_style))
    story.append(Spacer(1, 6))

    # Header fields in a two-column grid
    header_fields = tpl["schema"]["header_fields"]
    rows = []
    pair: list = []
    for f in header_fields:
        cell = [
            Paragraph(f["label"].upper(), label_style),
            Paragraph(_val(header, f["key"]) or "—", value_style),
        ]
        pair.append(cell)
        if len(pair) == 2:
            rows.append([pair[0], pair[1]])
            pair = []
    if pair:
        rows.append([pair[0], ""])

    if rows:
        header_table = Table(rows, colWidths=[85 * mm, 85 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 12))

    # Items table
    cols = tpl["schema"]["item_columns"]
    head_row = [c["label"] for c in cols]
    body = []
    for it in items:
        row = []
        for c in cols:
            v = it.get(c["key"], "")
            if c.get("type") == "number":
                row.append(_fmt_num(v))
            else:
                row.append(Paragraph(str(v or ""), value_style))
        body.append(row)

    if body:
        table = Table([head_row] + body, repeatRows=1, colWidths=_item_col_widths(cols))
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (-3, 1), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 10))

    # Totals
    totals_cfg = tpl["schema"]["totals"]
    if totals_cfg:
        t_rows = [[t["label"], _fmt_num(totals.get(t["key"], ""))] for t in totals_cfg]
        t_table = Table(t_rows, colWidths=[140 * mm, 30 * mm], hAlign="RIGHT")
        t_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#0A0A0B")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(t_table)

    # Footer terms for quotation
    if document_type == "QUOTATION":
        story.append(Spacer(1, 14))
        story.append(Paragraph("<b>TERMS AND CONDITIONS</b>", value_style))
        story.append(Paragraph(f"Payment Term: {header.get('payment_terms') or '—'}", value_style))
        story.append(Paragraph(f"Price Validity: {header.get('price_validity') or '—'}", value_style))
        story.append(Spacer(1, 18))
        story.append(Paragraph(f"Issued by: {header.get('issued_by') or '—'}", value_style))

    doc.build(story)
    return buf.getvalue()


def _item_col_widths(cols):
    # Give description the most space
    total = 170 * mm
    weights = []
    for c in cols:
        if c["key"] == "description":
            weights.append(3.5)
        elif c["key"] in ("amount", "total_cost", "unit_cost", "unit_rate"):
            weights.append(1.2)
        else:
            weights.append(1.0)
    s = sum(weights)
    return [total * w / s for w in weights]
