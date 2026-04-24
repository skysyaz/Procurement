import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorText } from "../lib/api";
import { Key, Receipt } from "@phosphor-icons/react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (ex) {
      setErr(apiErrorText(ex));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 pf-grid-bg">
      <form onSubmit={submit} className="pf-surface p-10 w-full max-w-md" data-testid="forgot-page">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 bg-[#0A0A0B] flex items-center justify-center">
            <Receipt size={16} color="#fff" weight="bold" />
          </div>
          <div className="font-display text-[18px] font-bold leading-none">ProcureFlow</div>
        </div>
        <div className="pf-overline mb-2">Reset</div>
        <h1 className="font-display text-[28px] font-bold tracking-tight leading-none">Forgot your password?</h1>
        <p className="text-[13px] text-[#52525B] mt-2">We'll email you a secure reset link valid for 1 hour.</p>

        {sent ? (
          <div className="mt-8 text-center py-8">
            <Key size={36} weight="bold" color="#047857" className="mx-auto" />
            <div className="mt-4 font-display text-[18px] font-semibold">Check your inbox</div>
            <p className="text-[13px] text-[#52525B] mt-2">If an account exists for <b>{email}</b>, a reset link is on its way.</p>
            <Link to="/login" className="pf-btn pf-btn-secondary mt-6 inline-flex" data-testid="forgot-back-login">Back to sign in</Link>
          </div>
        ) : (
          <>
            <div className="mt-6 space-y-4">
              <label className="block">
                <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Email</div>
                <input className="pf-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email" />
              </label>
              {err && <div className="text-[12px] text-[#B91C1C]" data-testid="forgot-error">{err}</div>}
              <button className="pf-btn pf-btn-primary w-full justify-center" disabled={loading} data-testid="forgot-submit">
                <Key size={14} weight="bold" /> {loading ? "Sending…" : "Send reset link"}
              </button>
            </div>
            <div className="text-[12px] text-[#71717A] mt-6">
              Remembered it? <Link to="/login" className="text-[#0F52BA] hover:underline">Sign in</Link>
            </div>
          </>
        )}
      </form>
    </div>
  );
}
