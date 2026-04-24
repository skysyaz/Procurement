import React, { useEffect, useState } from "react";
import { api, apiErrorText } from "../lib/api";
import { useAuth } from "../lib/auth";

const ROLES = ["admin", "manager", "user", "viewer"];

export default function AdminUsers() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");

  const load = async () => {
    try { const r = await api.get("/admin/users"); setUsers(r.data); }
    catch (e) { setErr(apiErrorText(e)); }
  };
  useEffect(() => { load(); }, []);

  const changeRole = async (id, role) => {
    try { await api.put(`/admin/users/${id}/role`, { role }); await load(); }
    catch (e) { alert(apiErrorText(e)); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try { await api.delete(`/admin/users/${id}`); await load(); }
    catch (e) { alert(apiErrorText(e)); }
  };

  return (
    <div className="p-10 pf-fade-up" data-testid="admin-users-page">
      <div className="mb-8">
        <div className="pf-overline mb-2">Administration</div>
        <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Users</h1>
        <p className="text-[13px] text-[#52525B] mt-2">Manage team members and their access level.</p>
      </div>
      {err && <div className="text-[12px] text-[#B91C1C] mb-4">{err}</div>}
      <div className="pf-surface">
        <table className="pf-table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} data-testid={`user-row-${u.id}`}>
                <td className="font-medium">{u.name}</td>
                <td className="text-[#52525B]">{u.email}</td>
                <td>
                  <select
                    className="pf-input w-[130px]"
                    value={u.role}
                    onChange={(e) => changeRole(u.id, e.target.value)}
                    disabled={u.id === me?.id}
                    data-testid={`role-select-${u.id}`}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="text-[#52525B] tabular-nums text-[12px]">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="text-right">
                  <button
                    className="pf-btn pf-btn-danger"
                    disabled={u.id === me?.id}
                    onClick={() => remove(u.id)}
                    data-testid={`del-user-${u.id}`}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
