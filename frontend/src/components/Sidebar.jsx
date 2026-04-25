import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  GridFour, UploadSimple, FileText, PlusCircle, Receipt, Cube,
  Users, ListBullets, SignOut, PencilRuler, ChartBar,
} from "@phosphor-icons/react";
import { useAuth, can } from "../lib/auth";

const LINKS = [
  { to: "/", label: "Dashboard", icon: GridFour, end: true, minRole: "viewer" },
  { to: "/upload", label: "Upload & Extract", icon: UploadSimple, minRole: "user" },
  { to: "/documents", label: "Documents", icon: FileText, minRole: "viewer" },
  { to: "/create", label: "Create Document", icon: PlusCircle, minRole: "user" },
  { to: "/templates", label: "Templates", icon: Cube, minRole: "viewer" },
  { to: "/reports", label: "Reports", icon: ChartBar, minRole: "viewer" },
];

const ADMIN_LINKS = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/templates", label: "Templates", icon: PencilRuler },
  { to: "/admin/audit", label: "Audit Log", icon: ListBullets },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <aside className="w-[240px] border-r border-[#E5E7EB] bg-[#FAFAFA] flex flex-col" data-testid="sidebar">
      <div className="px-5 py-5 border-b border-[#E5E7EB]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-[#0A0A0B] flex items-center justify-center">
            <Receipt size={16} color="#fff" weight="bold" />
          </div>
          <div>
            <div className="font-display text-[15px] font-bold leading-tight tracking-tight">ProcureFlow</div>
            <div className="pf-overline mt-0.5">Procurement OS</div>
          </div>
        </div>
      </div>

      <nav className="py-3 flex-1 overflow-y-auto">
        <div className="pf-overline px-5 pb-2">Workspace</div>
        {LINKS.filter((l) => can(user, l.minRole)).map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}
            className={({ isActive }) => "pf-sidebar-link" + (isActive ? " active" : "")}
            data-testid={`nav-${l.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}>
            <l.icon size={16} />
            <span>{l.label}</span>
          </NavLink>
        ))}

        {user?.role === "admin" && (
          <>
            <div className="pf-overline px-5 pb-2 pt-4">Administration</div>
            {ADMIN_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to}
                className={({ isActive }) => "pf-sidebar-link" + (isActive ? " active" : "")}
                data-testid={`nav-admin-${l.label.toLowerCase()}`}>
                <l.icon size={16} />
                <span>{l.label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-[#E5E7EB] p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 bg-[#0F52BA] text-white flex items-center justify-center text-[12px] font-semibold">
            {(user?.name || user?.email || "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-medium truncate" data-testid="user-name">{user?.name || user?.email}</div>
            <div className="text-[10px] text-[#71717A] uppercase tracking-[0.1em]" data-testid="user-role">{user?.role}</div>
          </div>
          <button
            onClick={async () => { await logout(); nav("/login"); }}
            className="pf-btn pf-btn-ghost" title="Sign out"
            data-testid="logout-btn"
          >
            <SignOut size={14} />
          </button>
        </div>
        <div className="text-[10px] text-[#A1A1AA]">v1.1 · OCR + AI</div>
      </div>
    </aside>
  );
}
