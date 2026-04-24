import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { TypeBadge } from "../components/Badges";
import StatusBadge from "../components/Badges";
import { Link } from "react-router-dom";
import { ArrowRight, FileText, UploadSimple, Plus, Lightning } from "@phosphor-icons/react";

const TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState(null);
  const { user } = useAuth();

  useEffect(() => { api.get("/dashboard/stats").then(r => setStats(r.data)); }, []);
  useEffect(() => {
    if (user?.role !== "admin") return;
    const load = () => api.get("/admin/queue-status").then(r => setQueue(r.data)).catch(() => {});
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [user]);

  return (
    <div className="p-10 pf-fade-up" data-testid="dashboard-page">
      <div className="flex items-start justify-between mb-10">
        <div>
          <div className="pf-overline mb-2">Control Room</div>
          <h1 className="font-display text-[40px] font-bold leading-none tracking-tight">Operations</h1>
          <p className="text-[13px] text-[#52525B] mt-2 max-w-md">
            Live snapshot of the procurement pipeline. Upload a document or draft a new one manually from a template.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/upload" className="pf-btn pf-btn-secondary" data-testid="dash-upload-cta">
            <UploadSimple size={14} /> Upload PDF
          </Link>
          <Link to="/create" className="pf-btn pf-btn-primary" data-testid="dash-create-cta">
            <Plus size={14} weight="bold" /> New document
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-0 pf-surface mb-8">
        <StatCell label="Total documents" val={stats?.total ?? "—"} testid="stat-total" />
        <StatCell label="Auto-extracted" val={stats?.by_status?.EXTRACTED ?? "—"} testid="stat-extracted" />
        <StatCell label="In review" val={stats?.by_status?.PROCESSING ?? "—"} testid="stat-processing" />
        <StatCell label="Manual drafts" val={stats?.by_status?.MANUAL_DRAFT ?? "—"} testid="stat-manual" last />
      </div>

      {queue && (
        <div className="pf-surface mb-8 p-5 flex flex-wrap items-center gap-6" data-testid="queue-status">
          <div className="flex items-center gap-2">
            <Lightning size={16} weight="bold" color={queue.celery_available ? "#047857" : "#92400E"} />
            <span className="pf-overline">Processing runner</span>
            <span className="font-display text-[14px] font-semibold uppercase tracking-[0.1em]">
              {queue.runner}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[13px] text-[#52525B]">
            <span className="pf-overline">In-flight</span>
            <span className="tabular-nums font-medium text-[#0A0A0B]">{queue.in_flight}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px] text-[#52525B]">
            <span className="pf-overline">Pending in Redis</span>
            <span className="tabular-nums font-medium text-[#0A0A0B]">{queue.pending_in_redis}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px] text-[#52525B]">
            <span className="pf-overline">Failed</span>
            <span className={"tabular-nums font-medium " + (queue.failed ? "text-[#B91C1C]" : "text-[#0A0A0B]")}>{queue.failed}</span>
          </div>
          <div className="ml-auto text-[11px] text-[#A1A1AA]">auto-refresh · 5s</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="pf-surface lg:col-span-2" data-testid="recent-list">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5E7EB]">
            <div>
              <div className="pf-overline">Recent activity</div>
              <div className="font-display text-[18px] font-semibold mt-1">Latest documents</div>
            </div>
            <Link to="/documents" className="text-[12px] text-[#0F52BA] flex items-center gap-1 hover:underline">
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {stats?.recent?.length ? (
            <table className="pf-table">
              <thead>
                <tr>
                  <th>Type</th><th>Filename / Ref</th><th>Status</th><th>Source</th><th>Created</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent.map((d) => (
                  <tr key={d.id}>
                    <td><TypeBadge type={d.type} /></td>
                    <td>
                      <Link to={`/review/${d.id}`} className="text-[#0A0A0B] hover:underline" data-testid={`recent-${d.id}`}>
                        {d.filename || `${d.type}-${d.id.slice(0,8)}`}
                      </Link>
                    </td>
                    <td><StatusBadge status={d.status} /></td>
                    <td className="text-[#52525B]">{d.source}</td>
                    <td className="tabular-nums text-[#52525B]">{new Date(d.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState />
          )}
        </div>

        <div className="pf-surface" data-testid="by-type-breakdown">
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="pf-overline">Breakdown</div>
            <div className="font-display text-[18px] font-semibold mt-1">By document type</div>
          </div>
          <div className="p-6 space-y-3">
            {TYPES.map((t) => {
              const count = stats?.by_type?.[t] ?? 0;
              const total = stats?.total || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={t} className="flex items-center gap-3">
                  <div className="w-[80px]"><TypeBadge type={t} /></div>
                  <div className="flex-1 h-[6px] bg-[#F4F4F5] overflow-hidden">
                    <div className="h-full bg-[#0A0A0B]" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-[36px] text-right tabular-nums text-[13px] font-medium">{count}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCell({ label, val, last, testid }) {
  return (
    <div className={"pf-stat " + (!last ? "border-r border-[#E5E7EB]" : "")} data-testid={testid}>
      <div className="pf-overline mb-2">{label}</div>
      <div className="val tabular-nums">{val}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="p-10 text-center">
      <FileText size={32} color="#A1A1AA" className="mx-auto" />
      <p className="text-[13px] text-[#71717A] mt-3">No documents yet. Upload a PDF or create one manually.</p>
    </div>
  );
}
