import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, can } from "../lib/auth";

export default function Protected({ children, minRole = "viewer" }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <div className="p-10 pf-pulse text-[#71717A]">Checking session…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!can(user, minRole)) {
    return (
      <div className="p-10" data-testid="forbidden">
        <div className="pf-overline mb-2">403</div>
        <h1 className="font-display text-[28px] font-bold">Insufficient role</h1>
        <p className="text-[13px] text-[#52525B] mt-2">You need <b>{minRole}</b> or higher to view this page.</p>
      </div>
    );
  }
  return children;
}
