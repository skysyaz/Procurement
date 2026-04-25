"""Aggregations powering the Dashboard and Reports pages.

All functions here are READ-ONLY MongoDB aggregations.  They run scoped to
the calling user's role: admin/manager see all docs, others see only their
own (``owner_id`` filter is layered on top of the base scope).

The aggregations pull totals out of ``extracted_data.totals.grand_total``
and the vendor name out of ``extracted_data.header.vendor_name`` (with
``client_name`` as fallback for QUOTATION-style docs where the
counter-party is the client, not a vendor).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# Statuses we consider "in pipeline" — uploaded/extracted but not yet finalized.
# Must align with DOC_STATUSES in server.py.
PIPELINE_STATUSES = ["UPLOADED", "PROCESSING", "EXTRACTED", "REVIEWED", "MANUAL_DRAFT"]
COMPLETED_STATUSES = ["FINAL"]


def _scope_for(user: Dict[str, Any]) -> Dict[str, Any]:
    """Mongo filter restricting to docs the user is allowed to see."""
    if user["role"] in {"admin", "manager"}:
        return {}
    return {"owner_id": user["id"]}


def _parse_iso(d: Optional[str]) -> Optional[datetime]:
    if not d:
        return None
    try:
        # Accept "YYYY-MM-DD" and full ISO.
        if len(d) == 10:
            return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(d.replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_filter(
    date_from: Optional[str], date_to: Optional[str]
) -> Dict[str, Any]:
    """Build a Mongo filter on ``created_at`` (stored as ISO strings)."""
    f: Dict[str, str] = {}
    if date_from:
        d = _parse_iso(date_from)
        if d:
            f["$gte"] = d.isoformat()
    if date_to:
        d = _parse_iso(date_to)
        if d:
            # Inclusive — bump by a day so anything stamped that calendar
            # day still counts.
            d = d + timedelta(days=1)
            f["$lt"] = d.isoformat()
    return {"created_at": f} if f else {}


def _grand_total(doc: Dict[str, Any]) -> float:
    """Pull a numeric grand-total out of the extracted payload, else 0.

    Falls back to ``subtotal`` if ``grand_total`` is empty so we still
    surface *some* spend even when the LLM missed the tax line.
    """
    totals = (doc.get("extracted_data") or {}).get("totals") or {}
    for k in ("grand_total", "total", "subtotal"):
        v = totals.get(k)
        if v in (None, ""):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


def _vendor(doc: Dict[str, Any]) -> str:
    """Best-effort vendor / counter-party name."""
    hdr = (doc.get("extracted_data") or {}).get("header") or {}
    for k in ("vendor_name", "supplier", "client_name", "company_name"):
        v = hdr.get(k)
        if v:
            return str(v).strip()
    return ""


def _month_key(iso_str: str) -> str:
    try:
        d = _parse_iso(iso_str)
        if d:
            return d.strftime("%Y-%m")
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------------------
# Public aggregations
# ---------------------------------------------------------------------------

async def dashboard_summary(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Return the new-look Dashboard payload.

    KPIs + monthly volume (last 6 months) + spend by type + top vendors
    + recent activity.
    """
    scope = _scope_for(user)
    total = await db.documents.count_documents(scope)

    pending = await db.documents.count_documents(
        {**scope, "status": {"$in": PIPELINE_STATUSES}}
    )

    # Pipeline value: sum of grand_totals for non-completed docs.
    pipeline_value = 0.0
    completed_value = 0.0
    by_type_spend: Dict[str, float] = {}
    by_type_count: Dict[str, int] = {}

    # First-of-this-month (UTC) for the "Completed This Month" KPI.
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()

    completed_this_month = await db.documents.count_documents({
        **scope,
        "status": {"$in": COMPLETED_STATUSES},
        "updated_at": {"$gte": month_start},
    })

    # Pull a manageable slice for client-side aggregation.  We avoid Mongo's
    # $expr-on-string-typed-totals in favour of Python sums for portability.
    cursor = db.documents.find(
        scope,
        {"_id": 0, "raw_text": 0},
    )

    # Last-6-months bucket pre-init so the chart shows zero-rows for empty
    # months instead of skipping them.
    months: List[str] = []
    for i in range(5, -1, -1):
        m = (now.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m")
        if m not in months:
            months.append(m)
    monthly: Dict[str, int] = {m: 0 for m in months}

    vendor_spend: Dict[str, float] = {}
    vendor_count: Dict[str, int] = {}

    async for d in cursor:
        gt = _grand_total(d)
        t = (d.get("type") or "OTHER").upper()
        by_type_count[t] = by_type_count.get(t, 0) + 1
        by_type_spend[t] = by_type_spend.get(t, 0.0) + gt

        if d.get("status") in COMPLETED_STATUSES:
            completed_value += gt
        else:
            pipeline_value += gt

        mk = _month_key(d.get("created_at") or "")
        if mk in monthly:
            monthly[mk] += 1

        v = _vendor(d)
        if v:
            vendor_spend[v] = vendor_spend.get(v, 0.0) + gt
            vendor_count[v] = vendor_count.get(v, 0) + 1

    top_vendors = sorted(
        [
            {"name": k, "spend": round(vendor_spend[k], 2), "count": vendor_count.get(k, 0)}
            for k in vendor_spend
        ],
        key=lambda x: x["spend"],
        reverse=True,
    )[:5]

    recent_cursor = db.documents.find(
        scope, {"_id": 0, "raw_text": 0, "extracted_data": 0},
    ).sort("created_at", -1).limit(8)
    recent = [d async for d in recent_cursor]

    return {
        "kpis": {
            "total_documents": total,
            "pending_approvals": pending,
            "pipeline_value": round(pipeline_value, 2),
            "completed_value": round(completed_value, 2),
            "completed_this_month": completed_this_month,
        },
        "monthly_volume": [{"month": m, "count": monthly[m]} for m in months],
        "spend_by_type": [
            {"type": t, "spend": round(by_type_spend.get(t, 0.0), 2),
             "count": by_type_count.get(t, 0)}
            for t in sorted(by_type_count, key=lambda x: by_type_count[x], reverse=True)
        ],
        "top_vendors": top_vendors,
        "recent": recent,
    }


async def reports_summary(
    db,
    user: Dict[str, Any],
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Filter docs by date/type/status and aggregate into the Reports view."""
    scope = _scope_for(user)
    q: Dict[str, Any] = {**scope, **_date_filter(date_from, date_to)}
    if doc_type and doc_type.upper() != "ALL":
        q["type"] = doc_type.upper()
    if status and status.upper() != "ALL":
        q["status"] = status.upper()

    cursor = db.documents.find(
        q, {"_id": 0, "raw_text": 0},
    ).sort("created_at", -1)

    docs: List[Dict[str, Any]] = []
    grand_total = 0.0
    by_type_spend: Dict[str, float] = {}
    by_type_count: Dict[str, int] = {}
    by_status_count: Dict[str, int] = {}
    vendor_spend: Dict[str, float] = {}
    vendor_count: Dict[str, int] = {}
    monthly: Dict[str, Dict[str, float]] = {}

    async for d in cursor:
        gt = _grand_total(d)
        grand_total += gt
        t = (d.get("type") or "OTHER").upper()
        s = (d.get("status") or "UNKNOWN").upper()
        by_type_count[t] = by_type_count.get(t, 0) + 1
        by_type_spend[t] = by_type_spend.get(t, 0.0) + gt
        by_status_count[s] = by_status_count.get(s, 0) + 1

        v = _vendor(d)
        if v:
            vendor_spend[v] = vendor_spend.get(v, 0.0) + gt
            vendor_count[v] = vendor_count.get(v, 0) + 1

        mk = _month_key(d.get("created_at") or "")
        if mk:
            bucket = monthly.setdefault(mk, {"count": 0, "spend": 0.0})
            bucket["count"] += 1
            bucket["spend"] += gt

        # Trim each doc to a slim card the frontend can show in a list.
        hdr = (d.get("extracted_data") or {}).get("header") or {}
        docs.append({
            "id": d.get("id"),
            "type": t,
            "status": s,
            "filename": d.get("filename"),
            "created_at": d.get("created_at"),
            "vendor": _vendor(d),
            "reference": (
                hdr.get("po_number") or hdr.get("invoice_number")
                or hdr.get("quotation_number") or hdr.get("reference_number") or ""
            ),
            "amount": round(gt, 2),
        })

    vendors = sorted(
        [
            {"name": k, "spend": round(vendor_spend[k], 2), "count": vendor_count.get(k, 0)}
            for k in vendor_spend
        ],
        key=lambda x: x["spend"],
        reverse=True,
    )

    return {
        "filters": {
            "from": date_from, "to": date_to,
            "type": doc_type or "ALL", "status": status or "ALL",
        },
        "kpis": {
            "doc_count": len(docs),
            "grand_total": round(grand_total, 2),
            "by_type_count": by_type_count,
            "by_status_count": by_status_count,
        },
        "vendors": vendors,
        "by_type": [
            {"type": t, "spend": round(by_type_spend.get(t, 0.0), 2),
             "count": by_type_count.get(t, 0)}
            for t in sorted(by_type_count, key=lambda x: by_type_count[x], reverse=True)
        ],
        "monthly": [
            {"month": m, "count": monthly[m]["count"], "spend": round(monthly[m]["spend"], 2)}
            for m in sorted(monthly.keys())
        ],
        "documents": docs,
    }
