import React from "react";

const MAP = {
  UPLOADED: { cls: "pf-badge-info", label: "Uploaded" },
  PROCESSING: { cls: "pf-badge-warn", label: "Processing" },
  EXTRACTED: { cls: "pf-badge-info", label: "Extracted" },
  REVIEWED: { cls: "pf-badge-ok", label: "Reviewed" },
  FINAL: { cls: "pf-badge-ok", label: "Final" },
  MANUAL_DRAFT: { cls: "pf-badge-neutral", label: "Manual Draft" },
};

export default function StatusBadge({ status }) {
  const s = MAP[status] || { cls: "pf-badge-neutral", label: status || "—" };
  return <span className={`pf-badge ${s.cls}`} data-testid={`status-${status}`}>{s.label}</span>;
}

export function TypeBadge({ type }) {
  const palette = {
    PO: "pf-badge-info",
    PR: "pf-badge-neutral",
    DO: "pf-badge-warn",
    QUOTATION: "pf-badge-ok",
    INVOICE: "pf-badge-err",
    OTHER: "pf-badge-neutral",
  };
  return <span className={`pf-badge ${palette[type] || "pf-badge-neutral"}`}>{type || "—"}</span>;
}
