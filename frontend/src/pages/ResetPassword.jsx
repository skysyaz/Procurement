import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, apiErrorText } from "../lib/api";
import { CheckCircle, Receipt } from "@phosphor-icons/react";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (password !== confirm) { setErr("Passwords don't match"); return; }
    if (password.length < 8) { setErr("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      setDone(true);
      setTimeout(() => nav("/login"), 1500);
    } catch (ex) {
      setErr(apiErrorText(ex));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 pf-grid-bg">
      <form onSubmit={submit} className="pf-surface p-10 w-full max-w-md" data-testid="reset-page">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 bg-[#0A0A0B] flex items-center justify-center">
            <Receipt size={16} color="#fff" weight="bold" />
          </div>
          <div className="font-display text-[18px] font-bold leading-none">ProcureFlow</div>
        </div>

        {done ? (
          <div className="text-center py-8">
            <CheckCircle size={40} weight="bold" color="#047857" className="mx-auto" />
            <div className="mt-4 font-display text-[20px] font-semibold">Password updated</div>
            <p className="text-[13px] text-[#52525B] mt-2">Redirecting to sign in…</p>
          </div>
        ) : (
          <>
            <div className="pf-overline mb-2">Reset</div>
            <h1 className="font-display text-[28px] font-bold tracking-tight leading-none">Set a new password</h1>
            <p className="text-[13px] text-[#52525B] mt-2">Minimum 8 characters.</p>

            {!token && (
              <div className="mt-6 text-[12px] text-[#B91C1C]">No reset token in the URL. Request a new link.</div>
            )}

            <div className="mt-6 space-y-4">
              <label className="block">
                <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">New password</div>
                <input className="pf-input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} data-testid="reset-password" />
              </label>
              <label className="block">
                <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Confirm password</div>
                <input className="pf-input" type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="reset-confirm" />
              </label>
              {err && <div className="text-[12px] text-[#B91C1C]" data-testid="reset-error">{err}</div>}
              <button className="pf-btn pf-btn-primary w-full justify-center" disabled={loading || !token} data-testid="reset-submit">
                {loading ? "Updating…" : "Update password"}
              </button>
            </div>
            <div className="text-[12px] text-[#71717A] mt-6">
              <Link to="/login" className="text-[#0F52BA] hover:underline">Back to sign in</Link>
            </div>
          </>
        )}
      </form>
    </div>
  );
}
