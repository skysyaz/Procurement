import React, { useState } from "react";
import { api, apiErrorText } from "../lib/api";
import { X, PaperPlaneTilt, CheckCircle } from "@phosphor-icons/react";

export default function EmailDialog({ docId, defaultSubject, onClose }) {
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState(defaultSubject || "");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    setErr(""); setSending(true);
    try {
      await api.post(`/documents/${docId}/email`, {
        to, cc: cc || null, subject, message,
      });
      setSent(true);
    } catch (ex) {
      setErr(apiErrorText(ex));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-[#0A0A0B]/40 z-50 flex items-center justify-center p-4" data-testid="email-dialog">
      <form onSubmit={send} className="pf-surface w-full max-w-lg p-8 bg-white relative">
        <button type="button" onClick={onClose} className="absolute top-4 right-4 pf-btn pf-btn-ghost" aria-label="Close" data-testid="email-close">
          <X size={14} />
        </button>
        <div className="pf-overline mb-2">Send PDF</div>
        <h2 className="font-display text-[22px] font-semibold tracking-tight">Email this document</h2>
        <p className="text-[12px] text-[#52525B] mt-1">The generated PDF will be attached automatically.</p>

        {sent ? (
          <div className="mt-8 text-center py-8">
            <CheckCircle size={40} weight="bold" color="#047857" className="mx-auto" />
            <div className="mt-4 font-display text-[18px] font-semibold">Sent to {to}</div>
            <button type="button" onClick={onClose} className="pf-btn pf-btn-primary mt-6" data-testid="email-done">Done</button>
          </div>
        ) : (
          <>
            <div className="mt-6 space-y-4">
              <Field label="To" required>
                <input className="pf-input" type="email" required value={to} onChange={(e) => setTo(e.target.value)} data-testid="email-to" />
              </Field>
              <Field label="CC (optional)">
                <input className="pf-input" type="email" value={cc} onChange={(e) => setCc(e.target.value)} data-testid="email-cc" />
              </Field>
              <Field label="Subject">
                <input className="pf-input" value={subject} onChange={(e) => setSubject(e.target.value)} data-testid="email-subject" />
              </Field>
              <Field label="Message">
                <textarea className="pf-input" rows={4} value={message} onChange={(e) => setMessage(e.target.value)} data-testid="email-message" />
              </Field>
              {err && <div className="text-[12px] text-[#B91C1C]" data-testid="email-error">{err}</div>}
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button type="button" className="pf-btn pf-btn-secondary" onClick={onClose}>Cancel</button>
              <button className="pf-btn pf-btn-primary" disabled={sending} data-testid="email-send">
                <PaperPlaneTilt size={14} weight="bold" /> {sending ? "Sending…" : "Send"}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label className="block">
      <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">
        {label}{required && <span className="text-[#B91C1C] ml-1">*</span>}
      </div>
      {children}
    </label>
  );
}
