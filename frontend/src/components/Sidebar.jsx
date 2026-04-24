import React from "react";
import { NavLink } from "react-router-dom";
import {
  GridFour, UploadSimple, FileText, PlusCircle, Receipt, Cube,
} from "@phosphor-icons/react";

const LINKS = [
  { to: "/", label: "Dashboard", icon: GridFour, end: true },
  { to: "/upload", label: "Upload & Extract", icon: UploadSimple },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/create", label: "Create Document", icon: PlusCircle },
  { to: "/templates", label: "Templates", icon: Cube },
];

export default function Sidebar() {
  return (
    <aside className="w-[240px] border-r border-[#E5E7EB] bg-[#FAFAFA] flex flex-col" data-testid="sidebar">
      <div className="px-5 py-6 border-b border-[#E5E7EB]">
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
      <nav className="py-3 flex-1">
        <div className="pf-overline px-5 pb-2">Workspace</div>
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.end}
            className={({ isActive }) => "pf-sidebar-link" + (isActive ? " active" : "")}
            data-testid={`nav-${l.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
          >
            <l.icon size={16} />
            <span>{l.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 text-[11px] text-[#71717A] border-t border-[#E5E7EB]">
        v1.0 · OCR + AI extraction
      </div>
    </aside>
  );
}
