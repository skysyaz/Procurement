"""Document template definitions. Built-in defaults are kept in code; admins
can override or add new types via the `document_templates` collection (see
`server.py` admin endpoints and `load_effective_templates`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "PO": {
        "document_type": "PO",
        "label": "Purchase Order",
        "schema": {
            "header_fields": [
                {"key": "po_number", "label": "PO Number", "type": "text", "required": True},
                {"key": "po_date", "label": "PO Date", "type": "date", "required": True},
                {"key": "delivery_date", "label": "Expected Delivery Date", "type": "date"},
                {"key": "vendor_name", "label": "Supplier Name", "type": "text", "required": True},
                {"key": "vendor_address", "label": "Supplier Address", "type": "textarea"},
                {"key": "delivery_address", "label": "Delivery Address", "type": "textarea"},
                {"key": "attention_person", "label": "Attention", "type": "text"},
                {"key": "payment_terms", "label": "Payment Terms", "type": "text"},
                {"key": "title", "label": "Title / Subject", "type": "text"},
                {"key": "issued_by", "label": "Issued By", "type": "text"},
                {"key": "issued_by_designation", "label": "Issuer Designation", "type": "text"},
                {"key": "approved_by", "label": "Approved By", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_cost", "label": "Unit Cost", "type": "number"},
                {"key": "total_cost", "label": "Total", "type": "number", "computed": "quantity*unit_cost"},
                {"key": "sst", "label": "SST", "type": "checkbox"},
            ],
            "totals": [
                {"key": "subtotal", "label": "Subtotal"},
                {"key": "tax", "label": "SST (8%)"},
                {"key": "grand_total", "label": "Grand Total"},
            ],
            "tax_rate": 0.08,
        },
    },
    "QUOTATION": {
        "document_type": "QUOTATION",
        "label": "Quotation",
        "schema": {
            "header_fields": [
                {"key": "quotation_number", "label": "Quotation / Ref No", "type": "text", "required": True},
                {"key": "reference_number", "label": "Reference Number", "type": "text"},
                {"key": "date", "label": "Date", "type": "date", "required": True},
                {"key": "vendor_name", "label": "Vendor", "type": "text", "required": True},
                {"key": "vendor_address", "label": "Vendor Address", "type": "textarea"},
                {"key": "client_name", "label": "Client Name", "type": "text", "required": True},
                {"key": "client_address", "label": "Client Address", "type": "textarea"},
                {"key": "attention_person", "label": "Attention", "type": "text"},
                {"key": "title", "label": "Title / Subject", "type": "text"},
                {"key": "location", "label": "Location", "type": "text"},
                {"key": "payment_terms", "label": "Payment Terms", "type": "text"},
                {"key": "price_validity", "label": "Price Validity", "type": "text"},
                {"key": "issued_by", "label": "Issued By", "type": "text"},
                {"key": "issued_by_designation", "label": "Issuer Designation", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "unit", "label": "Unit", "type": "text"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_rate", "label": "Unit Rate", "type": "number"},
                {"key": "amount", "label": "Amount", "type": "number", "computed": "quantity*unit_rate"},
                {"key": "sst", "label": "SST", "type": "checkbox"},
            ],
            "totals": [
                {"key": "subtotal", "label": "Sub-Total Amount"},
                {"key": "tax", "label": "SST (8%)"},
                {"key": "grand_total", "label": "Grand Total"},
            ],
            "tax_rate": 0.08,
        },
    },
    "PR": {
        "document_type": "PR",
        "label": "Purchase Request",
        "schema": {
            "header_fields": [
                {"key": "request_number", "label": "Request Number", "type": "text", "required": True},
                {"key": "request_date", "label": "Request Date", "type": "date", "required": True},
                {"key": "department", "label": "Department", "type": "text"},
                {"key": "project_reference", "label": "Project / Cost Centre", "type": "text"},
                {"key": "requester_name", "label": "Requester Name", "type": "text", "required": True},
                {"key": "requester_position", "label": "Requester Position", "type": "text"},
                {"key": "purpose", "label": "Purpose / Justification", "type": "textarea"},
                {"key": "title", "label": "Title / Subject", "type": "text"},
                {"key": "reviewer_name", "label": "Reviewer Name", "type": "text"},
                {"key": "reviewer_position", "label": "Reviewer Position", "type": "text"},
                {"key": "approver_name", "label": "Approver Name", "type": "text"},
                {"key": "approver_position", "label": "Approver Position", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_cost", "label": "Est. Unit Cost", "type": "number"},
                {"key": "total_cost", "label": "Estimated Cost", "type": "number", "computed": "quantity*unit_cost"},
            ],
            "totals": [
                {"key": "subtotal", "label": "Estimated Subtotal"},
                {"key": "grand_total", "label": "Estimated Total"},
            ],
            "tax_rate": 0,
        },
    },
    "DO": {
        "document_type": "DO",
        "label": "Delivery Order",
        "schema": {
            "header_fields": [
                {"key": "delivery_number", "label": "DO Number", "type": "text", "required": True},
                {"key": "delivery_date", "label": "Delivery Date", "type": "date", "required": True},
                {"key": "client_name", "label": "Deliver To (Client)", "type": "text", "required": True},
                {"key": "delivery_address", "label": "Delivery Address", "type": "textarea"},
                {"key": "reference_po", "label": "Reference PO", "type": "text"},
                {"key": "vehicle_no", "label": "Vehicle No", "type": "text"},
                {"key": "driver_name", "label": "Driver Name", "type": "text"},
                {"key": "received_by", "label": "Received By", "type": "text"},
                {"key": "issued_by", "label": "Issued By", "type": "text"},
                {"key": "issued_by_designation", "label": "Issuer Designation", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty Delivered", "type": "number"},
                {"key": "unit", "label": "Unit", "type": "text"},
            ],
            "totals": [],
            "tax_rate": 0,
        },
    },
    "INVOICE": {
        "document_type": "INVOICE",
        "label": "Invoice",
        "schema": {
            "header_fields": [
                {"key": "invoice_number", "label": "Invoice Number", "type": "text", "required": True},
                {"key": "invoice_date", "label": "Invoice Date", "type": "date", "required": True},
                {"key": "due_date", "label": "Payment Due Date", "type": "date"},
                {"key": "client_name", "label": "Bill To", "type": "text", "required": True},
                {"key": "client_address", "label": "Bill To Address", "type": "textarea"},
                {"key": "attention_person", "label": "Attention", "type": "text"},
                {"key": "po_reference", "label": "PO Reference", "type": "text"},
                {"key": "title", "label": "Title / Subject", "type": "text"},
                {"key": "payment_terms", "label": "Payment Terms", "type": "text"},
                {"key": "payment_method", "label": "Payment Method", "type": "text"},
                {"key": "bank_name", "label": "Bank Name", "type": "text"},
                {"key": "bank_account", "label": "Bank Account No.", "type": "text"},
                {"key": "bank_swift", "label": "SWIFT / Branch Code", "type": "text"},
                {"key": "issued_by", "label": "Issued By", "type": "text"},
                {"key": "issued_by_designation", "label": "Issuer Designation", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_price", "label": "Unit Price", "type": "number"},
                {"key": "amount", "label": "Amount", "type": "number", "computed": "quantity*unit_price"},
                {"key": "sst", "label": "SST", "type": "checkbox"},
            ],
            "totals": [
                {"key": "subtotal", "label": "Subtotal"},
                {"key": "tax", "label": "SST (8%)"},
                {"key": "grand_total", "label": "Grand Total"},
            ],
            "tax_rate": 0.08,
        },
    },
}


def get_template(document_type: str) -> Dict[str, Any]:
    return _runtime_templates.get(document_type.upper()) or DEFAULT_TEMPLATES.get(document_type.upper())


def list_templates() -> List[Dict[str, Any]]:
    seen = set(_runtime_templates.keys()) | set(DEFAULT_TEMPLATES.keys())
    out: List[Dict[str, Any]] = []
    for key in seen:
        tpl = _runtime_templates.get(key) or DEFAULT_TEMPLATES.get(key)
        if tpl:
            out.append(tpl)
    out.sort(key=lambda t: t["document_type"])
    return out


# Runtime overlay — merged with defaults, refreshed from MongoDB at startup and
# after every admin edit.
_runtime_templates: Dict[str, Dict[str, Any]] = {}


def set_runtime_templates(overrides: Dict[str, Dict[str, Any]]) -> None:
    _runtime_templates.clear()
    _runtime_templates.update({k.upper(): v for k, v in overrides.items()})


def upsert_runtime_template(tpl: Dict[str, Any]) -> None:
    _runtime_templates[tpl["document_type"].upper()] = tpl


def remove_runtime_template(document_type: str) -> None:
    _runtime_templates.pop(document_type.upper(), None)


def is_builtin(document_type: str) -> bool:
    return document_type.upper() in DEFAULT_TEMPLATES


def validate_schema(schema: Dict[str, Any]) -> Optional[str]:
    """Return an error message or None if the template schema is valid."""
    if not isinstance(schema, dict):
        return "schema must be an object"
    for key in ("header_fields", "item_columns", "totals"):
        if not isinstance(schema.get(key), list):
            return f"schema.{key} must be an array"
    allowed_types = {"text", "textarea", "number", "date", "checkbox"}
    for f in schema["header_fields"]:
        if not isinstance(f, dict) or not f.get("key") or not f.get("label"):
            return "each header_field needs key + label"
        if f.get("type", "text") not in allowed_types:
            return f"unsupported header_field type: {f.get('type')}"
    for c in schema["item_columns"]:
        if not isinstance(c, dict) or not c.get("key") or not c.get("label"):
            return "each item_column needs key + label"
        if c.get("type", "text") not in allowed_types:
            return f"unsupported item_column type: {c.get('type')}"
    for t in schema["totals"]:
        if not isinstance(t, dict) or not t.get("key") or not t.get("label"):
            return "each total needs key + label"
    tax = schema.get("tax_rate", 0)
    try:
        float(tax)
    except (TypeError, ValueError):
        return "tax_rate must be a number"
    return None
