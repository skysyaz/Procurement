import React, { useEffect, useMemo, useState, useCallback } from "react";
import { api } from "../lib/api";
import { TypeBadge } from "../components/Badges";
import StatusBadge from "../components/Badges";
import { Link } from "react-router-dom";
import {
  Printer, FileArrowDown, FunnelSimple, ArrowsClockwise, Buildings,
  ChartBar, FileText, ArrowRight,
} from "@phosphor-icons/react";

const TYPES = ["ALL", "PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];
const STATUSES = ["ALL", "PROCESSING", "EXTRACTED", "REVIEWED", "MANUAL_DRAFT", "APPROVED", "SENT", "FAILED"];

const RM = (n) => Number(n || 0).toLocaleString("en-MY", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

const todayISO = () => new Date().toISOString().slice(0, 10);
const monthsAgoISO = (n) => {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().slice(0, 10);
};

export default function Reports() {
  const [filters, setFilters] = useState({
    from: monthsAgoISO(3),
    to: todayISO(),
    type: "ALL",
    status: "ALL",
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const buildParams = useCallback(() => {
    const p = {};
    if (filters.from) p.from = filters.from;
    if (filters.to) p.to = filters.to;
    if (filters.type && filters.type !== "ALL") p.type = filters.type;
    if (filters.status && filters.status !== "ALL") p.status = filters.status;
    return p;
  }, [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/reports/summary", { params: buildParams() });
      setData(r.data);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => { load(); }, [load]);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const r = await api.get("/reports/pdf", {
        params: buildParams(),
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `procureflow-report-${filters.from || "all"}-to-${filters.to || "all"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const printPage = () => window.print();

  const k = data?.kpis || {};
  const vendors = data?.vendors || [];
  const docs = data?.documents || [];
  const byType = data?.by_type || [];

  const update = (patch) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <div className="p-4 sm:p-6 lg:p-10 pf-fade-up max-w-[1400px] mx-auto" data-testid="reports-page">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6 lg:mb-8 print:hidden">
        <div>
          <div className="pf-overline mb-2">Analytics</div>
          <h1 className="font-display text-[28px] sm:text-[32px] lg:text-[40px] font-bold leading-none tracking-tight">
            Reports
          </h1>
          <p className="text-[13px] text-[#52525B] mt-2 max-w-md">
            Procurement spend across types and vendors. Filter by type and date range, then print or export to PDF.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={printPage} className="pf-btn pf-btn-secondary" data-testid="reports-print-btn">
            <Printer size={14} /> Print
          </button>
          <button onClick={downloadPdf} disabled={downloading} className="pf-btn pf-btn-primary" data-testid="reports-pdf-btn">
            <FileArrowDown size={14} weight="bold" />
            {downloading ? "Generating…" : "Download PDF"}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="pf-surface mb-6 print:hidden" data-testid="reports-filters">
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-[#E5E7EB] flex items-center gap-2">
          <FunnelSimple size={14} />
          <div className="pf-overline">Filters</div>
          {loading && <ArrowsClockwise size={12} className="animate-spin text-[#71717A] ml-2" />}
        </div>
        <div className="p-4 sm:p-6 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <Field label="Type">
            <select
              value={filters.type}
              onChange={(e) => update({ type: e.target.value })}
              className="pf-input"
              data-testid="filter-type"
            >
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select
              value={filters.status}
              onChange={(e) => update({ status: e.target.value })}
              className="pf-input"
              data-testid="filter-status"
            >
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="From">
            <input
              type="date"
              value={filters.from}
              onChange={(e) => update({ from: e.target.value })}
              className="pf-input"
              data-testid="filter-from"
            />
          </Field>
          <Field label="To">
            <input
              type="date"
              value={filters.to}
              onChange={(e) => update({ to: e.target.value })}
              className="pf-input"
              data-testid="filter-to"
            />
          </Field>
        </div>
      </div>

      {/* Print-only header (the on-screen header is hidden when printing) */}
      <div className="hidden print:block mb-6 border-b border-[#0A0A0B] pb-4">
        <div className="font-display text-[22px] font-bold">Procurement Report</div>
        <div className="text-[12px] text-[#52525B]">
          Type: <b>{filters.type}</b> · Status: <b>{filters.status}</b> · From: <b>{filters.from || "—"}</b> · To: <b>{filters.to || "—"}</b>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <KpiCard label="Documents" value={k.doc_count ?? 0} testid="kpi-count" />
        <KpiCard label="Grand Total (RM)" value={`RM ${RM(k.grand_total || 0)}`} testid="kpi-grand-total" />
        <KpiCard
          label="By Type"
          value={k.by_type_count ? Object.keys(k.by_type_count).length : 0}
          subtitle={k.by_type_count ? Object.entries(k.by_type_count).map(([t, n]) => `${t}: ${n}`).join("  ·  ") : ""}
          testid="kpi-types"
        />
        <KpiCard
          label="By Status"
          value={k.by_status_count ? Object.keys(k.by_status_count).length : 0}
          subtitle={k.by_status_count ? Object.entries(k.by_status_count).map(([s, n]) => `${s}: ${n}`).join("  ·  ") : ""}
          testid="kpi-statuses"
        />
      </div>

      {/* Spend by type breakdown */}
      <div className="pf-surface mb-6">
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-[#E5E7EB]">
          <div className="pf-overline">Spend by Type</div>
        </div>
        <div className="p-4 sm:p-6">
          {byType.length ? (
            <div className="space-y-3">
              {byType.map((d) => {
                const max = Math.max(1, ...byType.map((x) => x.spend || 0));
                const pct = Math.max(4, Math.round(((d.spend || 0) / max) * 100));
                return (
                  <div key={d.type} className="flex items-center gap-3">
                    <div className="w-[80px] sm:w-[100px]"><TypeBadge type={d.type} /></div>
                    <div className="flex-1 h-[10px] bg-[#F4F4F5] overflow-hidden">
                      <div className="h-full bg-[#0A0A0B]" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="w-[110px] text-right text-[12px] tabular-nums font-medium">RM {RM(d.spend)}</div>
                    <div className="w-[28px] text-right text-[11px] tabular-nums text-[#71717A]">{d.count}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty icon={<ChartBar size={28} color="#A1A1AA" />} text="No data for the selected filters." />
          )}
        </div>
      </div>

      {/* Vendors by spend */}
      <div className="pf-surface mb-6">
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-[#E5E7EB]">
          <div className="pf-overline">Vendors by Spend</div>
        </div>
        {vendors.length ? (
          <div className="overflow-x-auto">
            <table className="pf-table">
              <thead>
                <tr><th>#</th><th>Vendor / Counter-Party</th><th className="text-right">Docs</th><th className="text-right">Spend (RM)</th></tr>
              </thead>
              <tbody>
                {vendors.map((v, i) => (
                  <tr key={v.name + i} data-testid={`vendor-row-${i}`}>
                    <td className="tabular-nums text-[#71717A]">{i + 1}</td>
                    <td className="font-medium">{v.name}</td>
                    <td className="text-right tabular-nums">{v.count}</td>
                    <td className="text-right tabular-nums font-semibold">{RM(v.spend)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon={<Buildings size={28} color="#A1A1AA" />} text="No vendor activity in this period." />
        )}
      </div>

      {/* Filtered documents list */}
      <div className="pf-surface">
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-[#E5E7EB] flex items-center justify-between">
          <div>
            <div className="pf-overline">Filtered Documents ({docs.length})</div>
          </div>
          <Link to="/documents" className="text-[12px] text-[#0F52BA] flex items-center gap-1 hover:underline print:hidden">
            View all <ArrowRight size={12} />
          </Link>
        </div>
        {docs.length ? (
          <div className="overflow-x-auto">
            <table className="pf-table">
              <thead>
                <tr><th>Date</th><th>Type</th><th>Reference</th><th>Vendor</th><th>Status</th><th className="text-right">Amount (RM)</th></tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td className="tabular-nums text-[#52525B] whitespace-nowrap">{(d.created_at || "").slice(0, 10)}</td>
                    <td><TypeBadge type={d.type} /></td>
                    <td className="font-medium">
                      <Link to={`/review/${d.id}`} className="hover:underline">{d.reference || d.filename || "—"}</Link>
                    </td>
                    <td>{d.vendor || <span className="text-[#A1A1AA]">—</span>}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td className="text-right tabular-nums font-semibold">{RM(d.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon={<FileText size={28} color="#A1A1AA" />} text="No documents match these filters." />
        )}
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="pf-overline mb-1">{label}</div>
      {children}
    </label>
  );
}

function KpiCard({ label, value, subtitle, testid }) {
  return (
    <div className="pf-surface p-4 sm:p-5" data-testid={testid}>
      <div className="pf-overline mb-2">{label}</div>
      <div className="font-display text-[20px] sm:text-[24px] font-bold tabular-nums leading-none truncate" title={value}>
        {value}
      </div>
      {subtitle && (
        <div className="text-[11px] text-[#71717A] mt-2 break-words" title={subtitle}>{subtitle}</div>
      )}
    </div>
  );
}

function Empty({ icon, text }) {
  return (
    <div className="p-10 text-center">
      <div className="flex justify-center mb-3">{icon}</div>
      <p className="text-[13px] text-[#71717A]">{text}</p>
    </div>
  );
}
