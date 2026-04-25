"""PDF generation for structured documents using ReportLab.

Two render paths:

* **branded** (``source == "MANUAL"``): full Quatriz template, modeled on the
  reference quotation supplied by the customer — big logo top-left, title in a
  bordered box top-right, structured To/Ref grid, item table with grid borders,
  Sub-total / SST / Grand Total stack, Terms & Conditions box, signature
  block, centered footer with Quatriz registration + address.
* **neutral** (``source == "AUTO"``): re-rendered extract for *uploaded*
  third-party documents (e.g. a Umobile invoice).  We never overwrite the
  original company's branding — we just render the fields we extracted in a
  clean, plain layout titled "Extracted Form".
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .templates import get_template


# ---- Branding ----------------------------------------------------------------
_BRAND_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = _BRAND_DIR / "quatriz_logo_pdf.png"

# Allow override via env so deployments can swap the branding without code
# changes.  Address uses ``|`` as a line separator.
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Quatriz System Sdn Bhd")
COMPANY_REG = os.environ.get("COMPANY_REG", "988952-X")
COMPANY_TAGLINE = os.environ.get("COMPANY_TAGLINE", "")
COMPANY_ADDRESS = os.environ.get(
    "COMPANY_ADDRESS",
    "Lot G3, HIVE 8, Taman Teknologi MRANTI, 57000, Bukit Jalil, Kuala Lumpur",
)
# Optional: override the bottom-right authorised-signatory designation/title
COMPANY_SIGNATORY_TITLE = os.environ.get("COMPANY_SIGNATORY_TITLE", "Authorised Signatory")
# Optional: invoice payment / banking details (rendered on INVOICE only).
BANK_NAME = os.environ.get("BANK_NAME", "")
BANK_ACCOUNT = os.environ.get("BANK_ACCOUNT", "")
BANK_SWIFT = os.environ.get("BANK_SWIFT", "")


def _sanitize_env(value: str) -> str:
    """Defensively strip another env-var name accidentally pasted into this one.

    On Render, users sometimes paste both ``COMPANY_REG`` and ``COMPANY_ADDRESS``
    into a single field, leaving ``"988952-X, COMPANY_ADDRESS=Lot G3,..."`` in
    the value.  Trim everything after a comma followed by ``WORD=`` so the
    footer renders the registration number cleanly.
    """
    if not value:
        return ""
    return re.split(r",\s*[A-Z][A-Z_]*\s*=", value, maxsplit=1)[0].strip()


COMPANY_REG = _sanitize_env(COMPANY_REG)
COMPANY_ADDRESS = _sanitize_env(COMPANY_ADDRESS)

# Constants shared by both paths.
PAGE_W = 210 * mm
LEFT = RIGHT = 18 * mm
USABLE_W = PAGE_W - LEFT - RIGHT  # 174mm usable width

NAVY = colors.HexColor("#0A2D5C")
INK = colors.HexColor("#0A0A0B")
MUTED = colors.HexColor("#52525B")
RULE = colors.HexColor("#0A0A0B")
SUBRULE = colors.HexColor("#9CA3AF")
BG_HEAD = colors.HexColor("#0A0A0B")


# ---- Helpers -----------------------------------------------------------------

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


def _styles():
    s = getSampleStyleSheet()
    return {
        "label": ParagraphStyle(
            "Label", parent=s["Normal"], fontSize=7.5, leading=9,
            textColor=MUTED, fontName="Helvetica-Bold",
        ),
        "value": ParagraphStyle(
            "Value", parent=s["Normal"], fontSize=9, leading=12,
            textColor=INK,
        ),
        "value_bold": ParagraphStyle(
            "ValueBold", parent=s["Normal"], fontSize=9, leading=12,
            textColor=INK, fontName="Helvetica-Bold",
        ),
        "small": ParagraphStyle(
            "Small", parent=s["Normal"], fontSize=8, leading=10,
            textColor=INK,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=s["Normal"], fontSize=8, leading=10,
            textColor=MUTED, alignment=1,  # center
        ),
        "footer_bold": ParagraphStyle(
            "FooterBold", parent=s["Normal"], fontSize=9, leading=11,
            textColor=INK, alignment=1, fontName="Helvetica-Bold",
        ),
        "h1": ParagraphStyle(
            "H1", parent=s["Heading1"], fontSize=16, leading=20,
            textColor=INK, fontName="Helvetica-Bold", alignment=1,
        ),
        "title_box": ParagraphStyle(
            "TitleBox", parent=s["Normal"], fontSize=10, leading=11,
            textColor=INK, fontName="Helvetica-Bold", alignment=1,
        ),
        "neutral_title": ParagraphStyle(
            "NeutralTitle", parent=s["Heading1"], fontSize=14, leading=18,
            textColor=INK, fontName="Helvetica-Bold",
        ),
    }


# ---- Branded layout (Quatriz quotation/PO/etc.) ------------------------------

def _branded_top_band(title: str, st) -> Table:
    """Logo on the left + bordered title box on the right.

    The two cells share the same row so the bottom edge is a perfectly
    straight line — no more zig-zag.
    """
    left_cell: List[Any] = []
    if LOGO_PATH.exists():
        try:
            left_cell.append(RLImage(str(LOGO_PATH), width=55 * mm, height=22 * mm, kind="proportional"))
        except Exception:  # noqa: BLE001
            left_cell.append(Paragraph(f"<b>{COMPANY_NAME}</b>", st["h1"]))
    else:
        left_cell.append(Paragraph(f"<b>{COMPANY_NAME}</b>", st["h1"]))

    # Compact bordered title box (matches the original Quatriz quotation:
    # ~40mm wide, ~7mm tall, plain white, thin black border, modest font).
    right_box = Table(
        [[Paragraph(title.upper(), st["title_box"])]],
        colWidths=[40 * mm],
        rowHeights=[7 * mm],
    )
    right_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ]
        )
    )

    band = Table(
        [[left_cell, right_box]],
        colWidths=[USABLE_W - 45 * mm, 45 * mm],
    )
    band.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("VALIGN", (1, 0), (1, 0), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return band


# Per-doc-type "To" block configuration.
# Each tuple: (left_label, name_key, address_key, attn_key)
# `name_key` falls back to client_name → vendor_name → requester_name when
# missing so older docs still render something instead of "—".
_TO_TARGETS: Dict[str, tuple] = {
    "QUOTATION": ("To",            "client_name",    "client_address",   "attention_person"),
    "INVOICE":   ("Bill To",       "client_name",    "client_address",   "attention_person"),
    "PO":        ("To (Supplier)", "vendor_name",    "vendor_address",   "attention_person"),
    "PR":        ("Requested By",  "requester_name", "department",       None),
    "DO":        ("Deliver To",    "client_name",    "delivery_address", "received_by"),
}

# Per-doc-type right-column reference rows (label, header_key).
_REF_ROWS: Dict[str, List[tuple]] = {
    "QUOTATION": [("Ref No", "quotation_number"), ("SST No", "sst_number"), ("Date", "date")],
    "INVOICE":   [("Invoice No", "invoice_number"), ("Date", "invoice_date"), ("Due Date", "due_date"), ("PO Ref", "po_reference")],
    "PO":        [("PO No", "po_number"), ("Date", "po_date"), ("Delivery Date", "delivery_date")],
    "PR":        [("Request No", "request_number"), ("Date", "request_date"), ("Department", "department")],
    "DO":        [("DO No", "delivery_number"), ("Date", "delivery_date"), ("Ref PO", "reference_po")],
}


def _branded_party_block(header: Dict[str, Any], st, doc_type: str = "") -> Table:
    """Left column: addressee block (To/Bill To/etc). Right: Ref/Date/Page grid."""
    cfg = _TO_TARGETS.get(doc_type.upper(), ("To", "client_name", "client_address", "attention_person"))
    label, name_key, addr_key, attn_key = cfg

    name = (
        _val(header, name_key)
        or _val(header, "client_name")
        or _val(header, "vendor_name")
        or _val(header, "requester_name")
        or "—"
    )
    addr = _val(header, addr_key) or _val(header, "client_address") or _val(header, "vendor_address")
    attn = _val(header, attn_key) if attn_key else (_val(header, "attention_person") or _val(header, "attn"))

    client_lines: List[Any] = [
        Paragraph(f"<b>{label}</b> &nbsp;: {name}", st["small"]),
    ]
    if addr:
        for line in [p.strip() for p in addr.split(",") if p.strip()]:
            client_lines.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{line}", st["small"]))
    if attn:
        client_lines.append(Spacer(1, 4))
        client_lines.append(Paragraph(f"<b>Attn</b> &nbsp; : {attn}", st["small"]))

    # Right column: doc-type aware ref/date/page rows.
    ref_rows: List[List[str]] = []
    rows_cfg = _REF_ROWS.get(doc_type.upper(), [
        ("Ref No", "reference_number"), ("Date", "date"),
    ])
    for row_label, key in rows_cfg:
        v = _val(header, key)
        if v:
            ref_rows.append([row_label, ":", v])
    ref_rows.append(["Page(s)", ":", "1"])

    ref_tbl = Table(ref_rows, colWidths=[18 * mm, 4 * mm, 50 * mm])
    ref_tbl.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    block = Table(
        [[client_lines, ref_tbl]],
        colWidths=[USABLE_W * 0.55, USABLE_W * 0.45],
    )
    block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return block


def _items_table(tpl: Dict[str, Any], items: List[Dict[str, Any]], st) -> Table:
    cols = tpl["schema"]["item_columns"]
    show_item_col = True

    head: List[str] = []
    if show_item_col:
        head.append("ITEM")
    for c in cols:
        label = c["label"].upper()
        if c.get("type") == "number" and c["key"] in ("unit_cost", "unit_rate", "amount", "total_cost", "subtotal"):
            label = f"{label}\n(RM)"
        head.append(label)

    body: List[List[Any]] = []
    for idx, it in enumerate(items, start=1):
        row: List[Any] = []
        if show_item_col:
            row.append(str(idx))
        for c in cols:
            v = it.get(c["key"], "")
            if c.get("type") == "number":
                row.append(_fmt_num(v))
            else:
                row.append(Paragraph(str(v or ""), st["value"]))
        body.append(row)

    # Empty placeholder rows so the table looks substantial even with 1-2 items
    while len(body) < 3:
        empty: List[Any] = [""] * (len(cols) + (1 if show_item_col else 0))
        body.append(empty)

    col_widths = _item_col_widths(cols, has_item_col=show_item_col)
    table = Table([head] + body, repeatRows=1, colWidths=col_widths)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ]
    # Right-align numeric columns (last 3 are typically qty, unit rate, amount).
    if show_item_col:
        # ITEM column centered
        style.append(("ALIGN", (0, 1), (0, -1), "CENTER"))
    # Find numeric col positions for right-align
    numeric_idx = []
    for i, c in enumerate(cols):
        if c.get("type") == "number":
            numeric_idx.append(i + (1 if show_item_col else 0))
    for ni in numeric_idx:
        style.append(("ALIGN", (ni, 1), (ni, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def _totals_table(tpl: Dict[str, Any], totals: Dict[str, Any], cols_count: int) -> Table:
    totals_cfg = tpl["schema"]["totals"]
    if not totals_cfg:
        return None  # type: ignore[return-value]

    rows = []
    for t in totals_cfg:
        rows.append([t["label"].upper(), _fmt_num(totals.get(t["key"], ""))])

    # Match width to the items table's right-most 2 columns approximately.
    label_col = USABLE_W * 0.78
    val_col = USABLE_W * 0.22

    tbl = Table(rows, colWidths=[label_col, val_col])
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, INK),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    # Highlight the LAST row (Grand Total)
    style.extend([
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, INK),
        ("FONTSIZE", (0, -1), (-1, -1), 10),
    ])
    tbl.setStyle(TableStyle(style))
    return tbl


def _terms_block(header: Dict[str, Any], st) -> Table | None:
    payment = _val(header, "payment_terms")
    validity = _val(header, "price_validity")
    if not (payment or validity):
        return None

    rows = []
    if payment:
        rows.append([Paragraph("Payment Term", st["small"]), Paragraph(payment, st["small"])])
    if validity:
        rows.append([Paragraph("Price Validity", st["small"]), Paragraph(validity, st["small"])])

    inner = Table(rows, colWidths=[35 * mm, 95 * mm])
    inner.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, INK),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    label_cell = Paragraph("<b>TERMS AND<br/>CONDITIONS</b>", st["small"])
    outer = Table([[label_cell, inner]], colWidths=[35 * mm, 130 * mm])
    outer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, 0), 0.4, INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return outer


def _signature_footer(header: Dict[str, Any], st) -> Table:
    issued_by = _val(header, "issued_by") or _val(header, "approved_by") or "—"
    designation = (
        _val(header, "issued_by_designation")
        or _val(header, "signatory_designation")
        or COMPANY_SIGNATORY_TITLE
    )
    sig = Paragraph(
        f"<br/><br/><br/><b>{issued_by}</b><br/>"
        f"<font size=8 color='#52525B'>{designation}</font>",
        st["small"],
    )
    return Table(
        [[sig, ""]],
        colWidths=[80 * mm, 90 * mm],
    )


# ---- Doc-type specific extra sections ----------------------------------------

def _approval_block(header: Dict[str, Any], st) -> Table:
    """3-cell approval grid for Purchase Requisitions."""
    cells = []
    for role_label, name_key, position_key in [
        ("Requested By", "requester_name", "requester_position"),
        ("Reviewed By", "reviewer_name", "reviewer_position"),
        ("Approved By", "approver_name", "approver_position"),
    ]:
        name = _val(header, name_key) or "—"
        position = _val(header, position_key) or ""
        cells.append(
            Paragraph(
                f"<font size=8 color='#52525B'><b>{role_label}</b></font><br/><br/><br/><br/>"
                f"<b>{name}</b><br/>"
                f"<font size=8 color='#52525B'>{position}</font>",
                st["small"],
            )
        )
    third = USABLE_W / 3
    tbl = Table([cells], colWidths=[third, third, third])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return tbl


def _do_receiver_block(header: Dict[str, Any], st) -> Table:
    """Vehicle/driver + received-by signature box for Delivery Orders."""
    rows = [
        [Paragraph("<b>Vehicle No</b>", st["small"]),
         Paragraph(_val(header, "vehicle_no") or "—", st["small"])],
        [Paragraph("<b>Driver Name</b>", st["small"]),
         Paragraph(_val(header, "driver_name") or "—", st["small"])],
        [Paragraph("<b>Received By</b>", st["small"]),
         Paragraph(
             "<br/><br/><br/>" + (_val(header, "received_by") or "")
             + "<br/><font size=8 color='#52525B'>Name &amp; Signature / Company Stamp</font>",
             st["small"],
         )],
    ]
    tbl = Table(rows, colWidths=[40 * mm, USABLE_W - 40 * mm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _invoice_bank_block(header: Dict[str, Any], st) -> Table | None:
    """Optional bank/payment details box for Invoices.

    Pulls from header fields first, then env vars (BANK_NAME / BANK_ACCOUNT /
    BANK_SWIFT). Returns None when nothing is set so we don't render an empty
    box.
    """
    bank = _val(header, "bank_name") or BANK_NAME
    account = _val(header, "bank_account") or BANK_ACCOUNT
    swift = _val(header, "bank_swift") or BANK_SWIFT
    method = _val(header, "payment_method") or ("Bank Transfer" if (bank or account) else "")
    if not (bank or account or swift or method):
        return None

    rows: List[List[Any]] = []
    if method:
        rows.append([Paragraph("<b>Payment Method</b>", st["small"]),
                     Paragraph(method, st["small"])])
    if bank:
        rows.append([Paragraph("<b>Bank</b>", st["small"]),
                     Paragraph(bank, st["small"])])
    if account:
        rows.append([Paragraph("<b>Account No.</b>", st["small"]),
                     Paragraph(account, st["small"])])
    if swift:
        rows.append([Paragraph("<b>SWIFT / Branch</b>", st["small"]),
                     Paragraph(swift, st["small"])])

    inner = Table(rows, colWidths=[35 * mm, 95 * mm])
    inner.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, INK),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    label_cell = Paragraph("<b>PAYMENT<br/>DETAILS</b>", st["small"])
    outer = Table([[label_cell, inner]], colWidths=[35 * mm, 130 * mm])
    outer.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.4, INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return outer


def _render_branded(document_type: str, data: Dict[str, Any]) -> bytes:
    tpl = get_template(document_type)
    if not tpl:
        raise ValueError(f"Unknown document type: {document_type}")

    header = data.get("header", {}) or {}
    items = data.get("items", []) or []
    totals = data.get("totals", {}) or {}

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=f"{tpl['label']} - {COMPANY_NAME}",
    )

    st = _styles()
    story: List[Any] = []
    story.append(_branded_top_band(tpl["label"], st))
    story.append(Spacer(1, 6))
    story.append(_branded_party_block(header, st, document_type))

    # TITLE row
    title_v = _val(header, "title") or _val(header, "subject") or _val(header, "description")
    if title_v:
        story.append(
            Paragraph(
                f"<b>TITLE</b> &nbsp;: &nbsp;{title_v}", st["small"],
            )
        )
        story.append(Spacer(1, 6))

    story.append(_items_table(tpl, items, st))
    tot = _totals_table(tpl, totals, len(tpl["schema"]["item_columns"]))
    if tot is not None:
        story.append(tot)

    terms = _terms_block(header, st)
    if terms is not None:
        story.append(Spacer(1, 12))
        story.append(terms)

    # Doc-type specific extra sections (after totals + terms, before signature).
    dtype_upper = document_type.upper()
    if dtype_upper == "PR":
        story.append(Spacer(1, 14))
        story.append(_approval_block(header, st))
    elif dtype_upper == "DO":
        story.append(Spacer(1, 14))
        story.append(_do_receiver_block(header, st))
    elif dtype_upper == "INVOICE":
        bank = _invoice_bank_block(header, st)
        if bank is not None:
            story.append(Spacer(1, 12))
            story.append(bank)

    story.append(Spacer(1, 18))
    story.append(_signature_footer(header, st))

    def _draw_footer(canvas, _doc):
        canvas.saveState()
        # Centered company line at the bottom of every page.
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
        # Page number top-right (small)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - RIGHT, 297 * mm - 8 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


# ---- Neutral layout (uploaded third-party docs) ------------------------------

def _render_neutral(
    document_type: str, data: Dict[str, Any], source_filename: str | None
) -> bytes:
    """Render the extracted data without any Quatriz branding.

    Used for third-party uploaded PDFs (e.g. Umobile invoices) — we never
    overwrite the original company's branding by stamping ours on top.  The
    output is a clean "Extracted Form" recap of the structured fields we
    pulled out, so the user can compare against the original.
    """
    tpl = get_template(document_type)
    if not tpl:
        raise ValueError(f"Unknown document type: {document_type}")

    header = data.get("header", {}) or {}
    items = data.get("items", []) or []
    totals = data.get("totals", {}) or {}

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Extracted Form - {tpl['label']}",
    )
    st = _styles()
    story: List[Any] = []

    story.append(Paragraph(f"EXTRACTED {tpl['label'].upper()}", st["neutral_title"]))
    if source_filename:
        story.append(Paragraph(f"<font color='#6B7280'>Source file: {source_filename}</font>", st["small"]))
    story.append(Paragraph(
        "<font color='#6B7280' size=8><i>This document recap was generated from the original third-party "
        "PDF. The original branding and formatting belong to the issuing party.</i></font>",
        st["small"],
    ))
    story.append(Spacer(1, 12))

    # Header fields in a clean 2-col table (no fancy branding)
    header_fields = tpl["schema"]["header_fields"]
    rows = []
    pair: list = []
    for f in header_fields:
        cell = [
            Paragraph(f["label"].upper(), st["label"]),
            Paragraph(_val(header, f["key"]) or "—", st["value"]),
        ]
        pair.append(cell)
        if len(pair) == 2:
            rows.append([pair[0], pair[1]])
            pair = []
    if pair:
        rows.append([pair[0], ""])
    if rows:
        h_tbl = Table(rows, colWidths=[USABLE_W / 2, USABLE_W / 2])
        h_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ]))
        story.append(h_tbl)
        story.append(Spacer(1, 12))

    # Items
    if items:
        story.append(_items_table(tpl, items, st))

    # Totals
    tot = _totals_table(tpl, totals, len(tpl["schema"]["item_columns"]))
    if tot is not None:
        story.append(tot)

    pdf.build(story)
    return buf.getvalue()


# ---- Public entry point ------------------------------------------------------

def render_document_pdf(
    document_type: str,
    data: Dict[str, Any],
    *,
    branded: bool = True,
    source_filename: str | None = None,
) -> bytes:
    if branded:
        return _render_branded(document_type, data)
    return _render_neutral(document_type, data, source_filename)


# ---- Column-width helper -----------------------------------------------------

def _item_col_widths(cols, has_item_col: bool = False):
    """Distribute available width across item-table columns.

    Description gets the lion's share; numeric columns are narrower so the
    digits aren't lost in big cells.  Adds an ITEM column up front when
    the branded layout asks for it.
    """
    total = USABLE_W
    weights = []
    if has_item_col:
        weights.append(0.7)
    for c in cols:
        if c["key"] == "description":
            weights.append(4.5)
        elif c["key"] in ("amount", "total_cost"):
            weights.append(1.4)
        elif c["key"] in ("unit_cost", "unit_rate"):
            weights.append(1.4)
        elif c["key"] in ("quantity", "qty"):
            weights.append(1.0)
        elif c["key"] == "unit":
            weights.append(1.0)
        else:
            weights.append(1.0)
    s = sum(weights)
    return [total * w / s for w in weights]
