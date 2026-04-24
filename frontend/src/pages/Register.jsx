import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { apiErrorText } from "../lib/api";
import { UserPlus, Receipt } from "@phosphor-icons/react";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const auth = useAuth();
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await auth.register(email, password, name);
      nav("/", { replace: true });
    } catch (err) {
      setError(apiErrorText(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 pf-grid-bg">
      <form onSubmit={submit} className="pf-surface p-10 w-full max-w-md" data-testid="register-page">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 bg-[#0A0A0B] flex items-center justify-center">
            <Receipt size={16} color="#fff" weight="bold" />
          </div>
          <div className="font-display text-[18px] font-bold leading-none">ProcureFlow</div>
        </div>
        <div className="pf-overline mb-2">Create account</div>
        <h1 className="font-display text-[28px] font-bold tracking-tight leading-none">Start using ProcureFlow</h1>
        <p className="text-[13px] text-[#52525B] mt-2">Minimum 8-character password. First user becomes admin.</p>

        <div className="mt-6 space-y-4">
          <label className="block">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Name</div>
            <input className="pf-input" required value={name} onChange={(e) => setName(e.target.value)} data-testid="reg-name" />
          </label>
          <label className="block">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Email</div>
            <input className="pf-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="reg-email" />
          </label>
          <label className="block">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Password</div>
            <input className="pf-input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} data-testid="reg-password" />
          </label>
          {error && <div className="text-[12px] text-[#B91C1C]" data-testid="reg-error">{error}</div>}
          <button className="pf-btn pf-btn-primary w-full justify-center" disabled={loading} data-testid="reg-submit">
            <UserPlus size={14} weight="bold" /> {loading ? "Creating…" : "Create account"}
          </button>
        </div>

        <div className="text-[12px] text-[#71717A] mt-6">
          Already have an account? <Link to="/login" className="text-[#0F52BA] hover:underline">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
