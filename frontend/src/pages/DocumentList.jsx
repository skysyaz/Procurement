import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import StatusBadge, { TypeBadge } from "../components/Badges";
import { MagnifyingGlass, Trash, FileArrowDown } from "@phosphor-icons/react";

const TYPES = ["ALL", "PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];
const STATUSES = ["ALL", "UPLOADED", "PROCESSING", "EXTRACTED", "REVIEWED", "FINAL", "MANUAL_DRAFT"];

export default function DocumentList() {
  const [docs, setDocs] = useState([]);
  const [type, setType] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const params = {};
    if (type !== "ALL") params.type = type;
    if (status !== "ALL") params.status = status;
    const r = await api.get("/documents", { params });
    setDocs(r.data);
    setLoading(false);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [type, status]);

  const remove = async (id) => {
    if (!window.confirm("Delete this document?")) return;
    await api.delete(`/documents/${id}`);
    load();
  };

  const filtered = docs.filter((d) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (d.filename || "").toLowerCase().includes(s)
      || (d.extracted_data?.header?.quotation_number || "").toLowerCase().includes(s)
      || (d.extracted_data?.header?.po_number || "").toLowerCase().includes(s)
      || (d.extracted_data?.header?.vendor_name || "").toLowerCase().includes(s);
  });

  return (
    <div className="p-10 pf-fade-up" data-testid="documents-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="pf-overline mb-2">Library</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Documents</h1>
          <p className="text-[13px] text-[#52525B] mt-2">Filter and open any procurement document.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/upload" className="pf-btn pf-btn-secondary" data-testid="list-upload-cta">Upload</Link>
          <Link to="/create" className="pf-btn pf-btn-primary" data-testid="list-create-cta">Create</Link>
        </div>
      </div>

      <div className="pf-surface">
        <div className="flex flex-wrap gap-3 items-center p-4 border-b border-[#E5E7EB]">
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-3 top-[10px] text-[#71717A]" />
            <input
              className="pf-input pl-9 w-[260px]"
              placeholder="Search by filename, number, vendor…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              data-testid="search-input"
            />
          </div>
          <select className="pf-input w-[160px]" value={type} onChange={(e) => setType(e.target.value)} data-testid="filter-type">
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select className="pf-input w-[170px]" value={status} onChange={(e) => setStatus(e.target.value)} data-testid="filter-status">
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="text-[12px] text-[#71717A] ml-auto tabular-nums">{filtered.length} records</div>
        </div>

        <table className="pf-table" data-testid="documents-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Reference / Filename</th>
              <th>Vendor / Client</th>
              <th>Status</th>
              <th>Source</th>
              <th className="text-right">Grand Total</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} className="text-center text-[#71717A] py-10 pf-pulse">Loading…</td></tr>}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={8} className="text-center text-[#71717A] py-10">No documents match the filters.</td></tr>
            )}
            {filtered.map((d) => {
              const h = d.extracted_data?.header || {};
              const ref = h.quotation_number || h.po_number || h.request_number || h.delivery_number || d.filename || d.id.slice(0, 8);
              const party = h.vendor_name || h.client_name || "—";
              const total = d.extracted_data?.totals?.grand_total;
              return (
                <tr key={d.id} data-testid={`doc-row-${d.id}`}>
                  <td><TypeBadge type={d.type} /></td>
                  <td>
                    <Link to={`/review/${d.id}`} className="font-medium hover:underline">
                      {ref}
                    </Link>
                  </td>
                  <td className="text-[#52525B]">{party}</td>
                  <td><StatusBadge status={d.status} /></td>
                  <td className="text-[#52525B] text-[12px]">{d.source}</td>
                  <td className="text-right tabular-nums">{total ? Number(total).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"}</td>
                  <td className="text-[#52525B] tabular-nums text-[12px]">{new Date(d.created_at).toLocaleDateString()}</td>
                  <td className="text-right">
                    <div className="flex gap-1 justify-end">
                      <a
                        href={`${process.env.REACT_APP_BACKEND_URL}/api/documents/${d.id}/pdf`}
                        target="_blank"
                        rel="noreferrer"
                        className="pf-btn pf-btn-ghost"
                        title="Download generated PDF"
                        data-testid={`pdf-${d.id}`}
                      >
                        <FileArrowDown size={14} />
                      </a>
                      <button className="pf-btn pf-btn-ghost" onClick={() => remove(d.id)} title="Delete" data-testid={`del-${d.id}`}>
                        <Trash size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
