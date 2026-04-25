import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorText } from "../lib/api";
import StatusBadge, { TypeBadge } from "../components/Badges";
import EmailDialog from "../components/EmailDialog";
import { useAuth, can } from "../lib/auth";
import {
  MagnifyingGlass, Trash, FileArrowDown, PaperPlaneTilt,
  CaretLeft, CaretRight, ArrowClockwise, CircleNotch,
} from "@phosphor-icons/react";

const TYPES = ["ALL", "PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];
const STATUSES = ["ALL", "UPLOADED", "PROCESSING", "EXTRACTED", "REVIEWED", "FINAL", "MANUAL_DRAFT", "FAILED"];

export default function DocumentList() {
  const { user } = useAuth();
  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [type, setType] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [emailingId, setEmailingId] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const r = await api.get("/documents", {
        params: {
          type: type === "ALL" ? undefined : type,
          status: status === "ALL" ? undefined : status,
          q: debounced || undefined,
          page, page_size: pageSize,
        },
      });
      setDocs(r.data.items); setTotal(r.data.total);
    } catch (e) { setErr(apiErrorText(e)); }
    finally { setLoading(false); }
  }, [type, status, debounced, page, pageSize]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [type, status, debounced]);

  const remove = async (id) => {
    if (!window.confirm("Delete this document?")) return;
    await api.delete(`/documents/${id}`);
    load();
  };

  const retryProcess = async (id) => {
    setRetryingId(id); setErr("");
    try {
      // Server runs OCR + classification + extraction inline; can take ~30s
      // for image-based PDFs.
      await api.post(`/documents/${id}/process`);
      await load();
    } catch (e) {
      setErr(apiErrorText(e));
    } finally {
      setRetryingId(null);
    }
  };

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="p-10 pf-fade-up" data-testid="documents-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="pf-overline mb-2">Library</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Documents</h1>
          <p className="text-[13px] text-[#52525B] mt-2">Filter, search, and open any procurement document.</p>
        </div>
        <div className="flex gap-2">
          {can(user, "user") && <Link to="/upload" className="pf-btn pf-btn-secondary">Upload</Link>}
          {can(user, "user") && <Link to="/create" className="pf-btn pf-btn-primary">Create</Link>}
        </div>
      </div>

      <div className="pf-surface">
        <div className="flex flex-wrap gap-3 items-center p-4 border-b border-[#E5E7EB]">
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-3 top-[10px] text-[#71717A]" />
            <input className="pf-input pl-9 w-[280px]" placeholder="Search vendor, client, PO/QO ref, filename…"
              value={search} onChange={(e) => setSearch(e.target.value)} data-testid="search-input" />
          </div>
          <select className="pf-input w-[160px]" value={type} onChange={(e) => setType(e.target.value)} data-testid="filter-type">
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select className="pf-input w-[170px]" value={status} onChange={(e) => setStatus(e.target.value)} data-testid="filter-status">
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="text-[12px] text-[#71717A] ml-auto tabular-nums">
            {total.toLocaleString()} records · page {page} of {pages}
          </div>
        </div>
        {err && <div className="p-4 text-[12px] text-[#B91C1C]">{err}</div>}

        <table className="pf-table" data-testid="documents-table">
          <thead>
            <tr>
              <th>Type</th><th>Reference / Filename</th><th>Vendor / Client</th>
              <th>Status</th><th>Owner</th><th className="text-right">Grand Total</th>
              <th>Created</th><th></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} className="text-center text-[#71717A] py-10 pf-pulse">Loading…</td></tr>}
            {!loading && docs.length === 0 && <tr><td colSpan={8} className="text-center text-[#71717A] py-10">No documents match the filters.</td></tr>}
            {docs.map((d) => {
              const h = d.extracted_data?.header || {};
              const ref = h.quotation_number || h.po_number || h.invoice_number || h.request_number || h.delivery_number || d.filename || d.id.slice(0, 8);
              const party = h.vendor_name || h.client_name || "—";
              const total = d.extracted_data?.totals?.grand_total;
              return (
                <tr key={d.id} data-testid={`doc-row-${d.id}`}>
                  <td><TypeBadge type={d.type} /></td>
                  <td><Link to={`/review/${d.id}`} className="font-medium hover:underline">{ref}</Link></td>
                  <td className="text-[#52525B]">{party}</td>
                  <td><StatusBadge status={d.status} /></td>
                  <td className="text-[#52525B] text-[12px]">{d.owner_email || "—"}</td>
                  <td className="text-right tabular-nums">{total ? Number(total).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"}</td>
                  <td className="text-[#52525B] tabular-nums text-[12px]">{new Date(d.created_at).toLocaleDateString()}</td>
                  <td className="text-right">
                    <div className="flex gap-1 justify-end">
                      {can(user, "user") && (d.status === "UPLOADED" || d.status === "FAILED") && (
                        <button
                          className="pf-btn pf-btn-ghost"
                          onClick={() => retryProcess(d.id)}
                          disabled={retryingId === d.id}
                          title="Re-run OCR & extraction"
                          data-testid={`retry-${d.id}`}
                        >
                          {retryingId === d.id
                            ? <CircleNotch size={14} className="animate-spin" />
                            : <ArrowClockwise size={14} />}
                        </button>
                      )}
                      <a href={`${process.env.REACT_APP_BACKEND_URL}/api/documents/${d.id}/pdf`} target="_blank" rel="noreferrer" className="pf-btn pf-btn-ghost" title="Generated PDF" data-testid={`pdf-${d.id}`}>
                        <FileArrowDown size={14} />
                      </a>
                      {can(user, "manager") && (
                        <button className="pf-btn pf-btn-ghost" onClick={() => setEmailingId(d.id)} title="Email PDF" data-testid={`email-${d.id}`}>
                          <PaperPlaneTilt size={14} />
                        </button>
                      )}
                      {can(user, "user") && (
                        <button className="pf-btn pf-btn-ghost" onClick={() => remove(d.id)} title="Delete" data-testid={`del-${d.id}`}>
                          <Trash size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="flex items-center justify-between p-3 border-t border-[#E5E7EB]">
          <select className="pf-input w-[110px]" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} data-testid="page-size">
            {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
          </select>
          <div className="flex items-center gap-2">
            <button className="pf-btn pf-btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} data-testid="prev-page">
              <CaretLeft size={14} /> Prev
            </button>
            <div className="text-[12px] tabular-nums text-[#52525B]">{page} / {pages}</div>
            <button className="pf-btn pf-btn-secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} data-testid="next-page">
              Next <CaretRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {emailingId && <EmailDialog docId={emailingId} onClose={() => setEmailingId(null)} />}
    </div>
  );
}
