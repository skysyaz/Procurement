"""Document template definitions. Schemas drive dynamic form rendering and
extraction prompts. Adding a new type is as simple as adding a new entry here.
"""
from typing import Any, Dict, List


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "PO": {
        "document_type": "PO",
        "label": "Purchase Order",
        "schema": {
            "header_fields": [
                {"key": "po_number", "label": "PO Number", "type": "text", "required": True},
                {"key": "po_date", "label": "PO Date", "type": "date", "required": True},
                {"key": "delivery_date", "label": "Delivery Date", "type": "date"},
                {"key": "vendor_name", "label": "Vendor Name", "type": "text", "required": True},
                {"key": "vendor_address", "label": "Vendor Address", "type": "textarea"},
                {"key": "company_name", "label": "Company Name", "type": "text"},
                {"key": "company_address", "label": "Company Address", "type": "textarea"},
                {"key": "attention_person", "label": "Attention", "type": "text"},
                {"key": "payment_terms", "label": "Payment Terms", "type": "text"},
                {"key": "prepared_by", "label": "Prepared By", "type": "text"},
                {"key": "approved_by", "label": "Approved By", "type": "text"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_cost", "label": "Unit Cost", "type": "number"},
                {"key": "total_cost", "label": "Total", "type": "number", "computed": "quantity*unit_cost"},
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
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "unit", "label": "Unit", "type": "text"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_rate", "label": "Unit Rate", "type": "number"},
                {"key": "amount", "label": "Amount", "type": "number", "computed": "quantity*unit_rate"},
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
                {"key": "requester_name", "label": "Requester Name", "type": "text", "required": True},
                {"key": "purpose", "label": "Purpose", "type": "textarea"},
            ],
            "item_columns": [
                {"key": "description", "label": "Description", "type": "textarea"},
                {"key": "quantity", "label": "Qty", "type": "number"},
                {"key": "unit_cost", "label": "Est. Unit Cost", "type": "number"},
                {"key": "total_cost", "label": "Total", "type": "number", "computed": "quantity*unit_cost"},
            ],
            "totals": [
                {"key": "subtotal", "label": "Subtotal"},
                {"key": "grand_total", "label": "Grand Total"},
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
                {"key": "vendor_name", "label": "Vendor Name", "type": "text", "required": True},
                {"key": "vendor_address", "label": "Vendor Address", "type": "textarea"},
                {"key": "received_by", "label": "Received By", "type": "text"},
                {"key": "reference_po", "label": "Reference PO", "type": "text"},
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
}


def get_template(document_type: str) -> Dict[str, Any]:
    return TEMPLATES.get(document_type.upper())


def list_templates() -> List[Dict[str, Any]]:
    return list(TEMPLATES.values())
