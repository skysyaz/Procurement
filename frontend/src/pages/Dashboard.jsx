import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { TypeBadge } from "../components/Badges";
import StatusBadge from "../components/Badges";
import { Link } from "react-router-dom";
import {
  ArrowRight, FileText, UploadSimple, Plus, Lightning,
  ChartBar, Buildings, Receipt, ClockClockwise,
} from "@phosphor-icons/react";

const TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];

const RM = (n) => {
  const x = Number(n || 0);
  return x.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [queue, setQueue] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setData(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    if (user?.role !== "admin") return;
    const load = () =>
      api.get("/admin/queue-status").then((r) => setQueue(r.data)).catch(() => {});
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [user]);

  const k = data?.kpis || {};
  const monthly = data?.monthly_volume || [];
  const byType = data?.spend_by_type || [];
  const topV = data?.top_vendors || [];
  const recent = data?.recent || [];

  return (
    <div className="p-4 sm:p-6 lg:p-10 pf-fade-up max-w-[1400px] mx-auto" data-testid="dashboard-page">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-8 lg:mb-10">
        <div>
          <div className="pf-overline mb-2">Control Room</div>
          <h1 className="font-display text-[28px] sm:text-[32px] lg:text-[40px] font-bold leading-none tracking-tight">
            Operations
          </h1>
          <p className="text-[13px] text-[#52525B] mt-2 max-w-md">
            Live snapshot of the procurement pipeline. Upload a document or draft a new one manually from a template.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/upload" className="pf-btn pf-btn-secondary" data-testid="dash-upload-cta">
            <UploadSimple size={14} /> Upload PDF
          </Link>
          <Link to="/create" className="pf-btn pf-btn-primary" data-testid="dash-create-cta">
            <Plus size={14} weight="bold" /> New document
          </Link>
        </div>
      </div>

      {/* KPI grid: 2 cols on mobile, 4 on tablet+ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <KpiCard
          label="Total Documents"
          value={k.total_documents ?? "—"}
          icon={<FileText size={16} weight="duotone" />}
          accent="#0F52BA"
          testid="kpi-total"
        />
        <KpiCard
          label="Pending Approvals"
          value={k.pending_approvals ?? "—"}
          icon={<ClockClockwise size={16} weight="duotone" />}
          accent="#B45309"
          testid="kpi-pending"
        />
        <KpiCard
          label="Pipeline Value"
          value={k.pipeline_value != null ? `RM ${RM(k.pipeline_value)}` : "—"}
          icon={<ChartBar size={16} weight="duotone" />}
          accent="#0A0A0B"
          testid="kpi-pipeline"
        />
        <KpiCard
          label="Completed This Month"
          value={k.completed_this_month ?? "—"}
          subtitle={k.completed_value != null ? `RM ${RM(k.completed_value)} value` : ""}
          icon={<Receipt size={16} weight="duotone" />}
          accent="#047857"
          testid="kpi-completed"
        />
      </div>

      {queue && (
        <div className="pf-surface mb-6 p-4 sm:p-5 flex flex-wrap items-center gap-x-6 gap-y-3" data-testid="queue-status">
          <div className="flex items-center gap-2">
            <Lightning size={16} weight="bold" color={queue.celery_available ? "#047857" : "#92400E"} />
            <span className="pf-overline">Runner</span>
            <span className="font-display text-[13px] font-semibold uppercase tracking-[0.08em]">{queue.runner}</span>
          </div>
          <Mini label="In-flight" val={queue.in_flight} />
          <Mini label="Pending" val={queue.pending_in_redis} />
          <Mini label="Failed" val={queue.failed} alert={queue.failed > 0} />
          <div className="ml-auto text-[11px] text-[#A1A1AA]">auto-refresh · 5s</div>
        </div>
      )}

      {/* Two charts side by side on lg+, stacked below */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mb-6">
        <Card title="Monthly Volume" subtitle="Documents created per month (last 6)">
          <MonthlyChart data={monthly} />
        </Card>
        <Card title="Spend by Type" subtitle="Total RM grouped by document type">
          <SpendByType data={byType} />
        </Card>
      </div>

      {/* Recent activity + Top vendors */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        <div className="pf-surface lg:col-span-2" data-testid="recent-list">
          <CardHeader
            title="Recent Activity"
            right={
              <Link to="/documents" className="text-[12px] text-[#0F52BA] flex items-center gap-1 hover:underline">
                View all <ArrowRight size={12} />
              </Link>
            }
          />
          {recent.length ? (
            <div className="overflow-x-auto">
              <table className="pf-table">
                <thead>
                  <tr><th>Type</th><th>Filename / Ref</th><th>Status</th><th>Source</th><th>Created</th></tr>
                </thead>
                <tbody>
                  {recent.map((d) => (
                    <tr key={d.id}>
                      <td><TypeBadge type={d.type} /></td>
                      <td>
                        <Link to={`/review/${d.id}`} className="text-[#0A0A0B] hover:underline">
                          {d.filename || `${d.type}-${(d.id || "").slice(0, 8)}`}
                        </Link>
                      </td>
                      <td><StatusBadge status={d.status} /></td>
                      <td className="text-[#52525B]">{d.source}</td>
                      <td className="tabular-nums text-[#52525B] whitespace-nowrap">
                        {d.created_at ? new Date(d.created_at).toLocaleString() : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon={<FileText size={28} color="#A1A1AA" />} text="No recent activity yet." />
          )}
        </div>

        <div className="pf-surface" data-testid="top-vendors">
          <CardHeader title="Top Vendors" subtitle="By total RM spend" />
          {topV.length ? (
            <div className="px-4 sm:px-6 py-4 space-y-3">
              {topV.map((v, i) => {
                const max = topV[0].spend || 1;
                const pct = Math.max(6, Math.round((v.spend / max) * 100));
                return (
                  <div key={v.name + i} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="w-5 text-[11px] text-[#71717A] tabular-nums">{i + 1}</span>
                      <span className="flex-1 text-[13px] font-medium truncate" title={v.name}>{v.name}</span>
                      <span className="text-[12px] tabular-nums text-[#0A0A0B] font-semibold">RM {RM(v.spend)}</span>
                    </div>
                    <div className="h-[4px] bg-[#F4F4F5] overflow-hidden ml-7">
                      <div className="h-full bg-[#0A0A0B]" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty icon={<Buildings size={28} color="#A1A1AA" />} text="No vendor data yet." />
          )}
        </div>
      </div>

      <div className="mt-6">
        <div className="pf-surface" data-testid="by-type-breakdown">
          <CardHeader title="Documents by Type" subtitle="Distribution across the procurement pipeline" />
          <div className="p-4 sm:p-6 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
            {TYPES.map((t) => {
              const row = byType.find((r) => r.type === t);
              const count = row?.count ?? 0;
              const total = byType.reduce((a, b) => a + (b.count || 0), 0) || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={t} className="flex items-center gap-3">
                  <div className="w-[80px]"><TypeBadge type={t} /></div>
                  <div className="flex-1 h-[6px] bg-[#F4F4F5] overflow-hidden">
                    <div className="h-full bg-[#0A0A0B]" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-[40px] text-right tabular-nums text-[13px] font-medium">{count}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- subcomponents */

function KpiCard({ label, value, subtitle, icon, accent, testid }) {
  return (
    <div className="pf-surface p-4 sm:p-5" data-testid={testid}>
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-7 h-7 flex items-center justify-center text-white"
          style={{ background: accent }}
        >
          {icon}
        </span>
        <span className="pf-overline">{label}</span>
      </div>
      <div className="font-display text-[22px] sm:text-[26px] font-bold tabular-nums leading-none">
        {value}
      </div>
      {subtitle && <div className="text-[11px] text-[#71717A] mt-2 truncate">{subtitle}</div>}
    </div>
  );
}

function Mini({ label, val, alert }) {
  return (
    <div className="flex items-center gap-2 text-[13px] text-[#52525B]">
      <span className="pf-overline">{label}</span>
      <span className={"tabular-nums font-medium " + (alert ? "text-[#B91C1C]" : "text-[#0A0A0B]")}>
        {val}
      </span>
    </div>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <div className="pf-surface">
      <CardHeader title={title} subtitle={subtitle} />
      <div className="p-4 sm:p-6">{children}</div>
    </div>
  );
}

function CardHeader({ title, subtitle, right }) {
  return (
    <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-[#E5E7EB] gap-3">
      <div className="min-w-0">
        <div className="pf-overline truncate">{title}</div>
        {subtitle && <div className="text-[11px] text-[#71717A] mt-0.5 truncate">{subtitle}</div>}
      </div>
      {right}
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

function MonthlyChart({ data }) {
  const max = useMemo(
    () => Math.max(1, ...data.map((d) => d.count || 0)),
    [data]
  );
  if (!data.length) return <Empty icon={<ChartBar size={28} color="#A1A1AA" />} text="No data yet." />;
  return (
    <div className="flex items-end gap-2 sm:gap-3 h-[160px]" role="img" aria-label="Monthly volume bar chart">
      {data.map((d) => {
        const h = Math.max(2, Math.round(((d.count || 0) / max) * 140));
        return (
          <div key={d.month} className="flex-1 flex flex-col items-center gap-1 min-w-0">
            <div className="text-[10px] tabular-nums text-[#52525B]">{d.count || 0}</div>
            <div className="w-full bg-[#F4F4F5]" style={{ height: 140 }}>
              <div className="bg-[#0A0A0B] w-full" style={{ height: h, marginTop: 140 - h }} />
            </div>
            <div className="text-[10px] text-[#71717A] truncate w-full text-center">{d.month}</div>
          </div>
        );
      })}
    </div>
  );
}

function SpendByType({ data }) {
  if (!data.length || data.every((d) => !d.spend)) {
    return <Empty icon={<ChartBar size={28} color="#A1A1AA" />} text="No spend data yet." />;
  }
  const max = Math.max(1, ...data.map((d) => d.spend || 0));
  return (
    <div className="space-y-3">
      {data.map((d) => {
        const pct = Math.max(4, Math.round(((d.spend || 0) / max) * 100));
        return (
          <div key={d.type} className="flex items-center gap-3">
            <div className="w-[88px]"><TypeBadge type={d.type} /></div>
            <div className="flex-1 h-[10px] bg-[#F4F4F5] overflow-hidden">
              <div className="h-full bg-[#0A0A0B]" style={{ width: `${pct}%` }} />
            </div>
            <div className="w-[110px] text-right text-[12px] tabular-nums font-medium text-[#0A0A0B]">
              RM {RM(d.spend)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
