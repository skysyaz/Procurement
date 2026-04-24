import React, { useEffect, useState } from "react";
import { api, apiErrorText } from "../lib/api";

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [actionFilter, setActionFilter] = useState("");
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      const params = {};
      if (actionFilter) params.action = actionFilter;
      const r = await api.get("/audit-logs", { params });
      setLogs(r.data);
    } catch (e) { setErr(apiErrorText(e)); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [actionFilter]);

  return (
    <div className="p-10 pf-fade-up" data-testid="audit-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="pf-overline mb-2">Administration</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Audit Log</h1>
          <p className="text-[13px] text-[#52525B] mt-2">Every write action across documents and users.</p>
        </div>
        <select
          className="pf-input w-[220px]"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          data-testid="audit-action-filter"
        >
          <option value="">All actions</option>
          {["USER_LOGIN", "USER_REGISTER", "USER_LOGOUT", "USER_ROLE_CHANGE", "USER_DELETE",
            "DOC_UPLOAD", "DOC_PROCESS", "DOC_BULK_UPLOAD", "DOC_REVIEW",
            "DOC_CREATE_MANUAL", "DOC_DELETE", "DOC_EMAIL"]
            .map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      {err && <div className="text-[12px] text-[#B91C1C] mb-4">{err}</div>}
      <div className="pf-surface">
        <table className="pf-table">
          <thead>
            <tr>
              <th>When</th><th>Actor</th><th>Role</th><th>Action</th>
              <th>Target</th><th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && <tr><td colSpan={6} className="text-center text-[#71717A] py-10">No activity yet.</td></tr>}
            {logs.map((l) => (
              <tr key={l.id} data-testid={`audit-row-${l.id}`}>
                <td className="tabular-nums text-[12px] text-[#52525B] whitespace-nowrap">
                  {new Date(l.created_at).toLocaleString()}
                </td>
                <td className="text-[13px]">{l.actor_email || "—"}</td>
                <td className="text-[11px] uppercase tracking-[0.1em] text-[#71717A]">{l.actor_role}</td>
                <td><span className="pf-badge pf-badge-neutral">{l.action}</span></td>
                <td className="text-[12px] text-[#52525B] font-mono-tab">{l.target_type}:{(l.target_id || "").slice(0, 8)}</td>
                <td className="text-[11px] text-[#52525B] font-mono-tab max-w-[340px] truncate">{JSON.stringify(l.meta || {})}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
