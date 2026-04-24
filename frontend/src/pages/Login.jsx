import React, { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { apiErrorText } from "../lib/api";
import { SignIn, Receipt } from "@phosphor-icons/react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const auth = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = loc.state?.from || "/";

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await auth.login(email, password);
      nav(from, { replace: true });
    } catch (err) {
      setError(apiErrorText(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2" data-testid="login-page">
      <div className="hidden lg:flex flex-col justify-between bg-[#0A0A0B] text-white p-12 pf-grid-bg" style={{ backgroundImage: "linear-gradient(rgba(10,10,11,0.85), rgba(10,10,11,0.95)), linear-gradient(#1f1f22 1px, transparent 1px), linear-gradient(90deg, #1f1f22 1px, transparent 1px)", backgroundSize: "auto, 40px 40px, 40px 40px" }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-white flex items-center justify-center">
            <Receipt size={18} color="#0A0A0B" weight="bold" />
          </div>
          <div>
            <div className="font-display text-[20px] font-bold leading-none">ProcureFlow</div>
            <div className="pf-overline text-white/60 mt-1">Procurement OS</div>
          </div>
        </div>
        <div>
          <div className="pf-overline text-white/60 mb-3">What's inside</div>
          <ul className="space-y-3 text-[14px] text-white/80 max-w-sm">
            <li>— Drop a PDF and the pipeline auto-classifies it as PO / PR / DO / Quotation / Invoice.</li>
            <li>— Gemini 2.5 Flash extracts structured line items directly into your schema.</li>
            <li>— Draft new documents from templates and generate a styled PDF instantly.</li>
            <li>— Email quotes, run bulk extractions, track every action in the audit log.</li>
          </ul>
        </div>
        <div className="text-[11px] text-white/40">v1.1 · multi-user · audit logged</div>
      </div>

      <div className="flex items-center justify-center p-10">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="pf-overline mb-2">Sign in</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Welcome back</h1>
          <p className="text-[13px] text-[#52525B] mt-2">Use your ProcureFlow credentials.</p>

          <div className="mt-8 space-y-4">
            <label className="block">
              <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Email</div>
              <input className="pf-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" autoComplete="email" />
            </label>
            <label className="block">
              <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Password</div>
              <input className="pf-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password" autoComplete="current-password" />
            </label>
            {error && <div className="text-[12px] text-[#B91C1C]" data-testid="login-error">{error}</div>}
            <button className="pf-btn pf-btn-primary w-full justify-center" disabled={loading} data-testid="login-submit">
              <SignIn size={14} weight="bold" /> {loading ? "Signing in…" : "Sign in"}
            </button>
          </div>

          <div className="text-[12px] text-[#71717A] mt-6">
            No account? <Link to="/register" className="text-[#0F52BA] hover:underline" data-testid="link-register">Create one</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
