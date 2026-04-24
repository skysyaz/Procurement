import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import DocumentForm from "../components/DocumentForm";
import { FloppyDisk, FileArrowDown } from "@phosphor-icons/react";

const TYPES = ["QUOTATION", "PO", "PR", "DO"];

export default function CreateDocument() {
  const [type, setType] = useState("QUOTATION");
  const [template, setTemplate] = useState(null);
  const [value, setValue] = useState({ header: {}, items: [], totals: {} });
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      const r = await api.get(`/templates/${type}`);
      setTemplate(r.data);
      setValue({ header: {}, items: [], totals: {} });
      setSavedId(null);
    })();
  }, [type]);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.post("/documents/create", { type, data: value });
      setSavedId(r.data.id);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-10 pf-fade-up" data-testid="create-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="pf-overline mb-2">Manual mode</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Create Document</h1>
          <p className="text-[13px] text-[#52525B] mt-2 max-w-xl">
            Fill a schema-driven form matching your company’s document layout. Line items auto-calculate, taxes and grand totals roll up automatically.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="pf-overline">Type</div>
          <div className="flex border border-[#E5E7EB]">
            {TYPES.map((t) => (
              <button
                key={t}
                className={"px-3 py-1.5 text-[12px] font-medium " + (t === type ? "bg-[#0A0A0B] text-white" : "bg-white text-[#52525B] hover:bg-[#F4F4F5]")}
                onClick={() => setType(t)}
                data-testid={`type-${t}`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="pf-surface p-8">
        {template ? <DocumentForm template={template} value={value} onChange={setValue} /> : <div className="pf-pulse text-[#71717A]">Loading template…</div>}
      </div>

      <div className="flex justify-end gap-2 mt-6">
        {savedId && (
          <>
            <a href={`${process.env.REACT_APP_BACKEND_URL}/api/documents/${savedId}/pdf`} target="_blank" rel="noreferrer" className="pf-btn pf-btn-secondary" data-testid="create-view-pdf">
              <FileArrowDown size={14} /> View generated PDF
            </a>
            <button className="pf-btn pf-btn-primary" onClick={() => nav(`/review/${savedId}`)} data-testid="create-open-review">
              Open in review
            </button>
          </>
        )}
        <button className="pf-btn pf-btn-primary" onClick={save} disabled={saving} data-testid="create-save-btn">
          <FloppyDisk size={14} /> {saving ? "Saving…" : savedId ? "Saved ✓  ·  Save as new" : "Save document"}
        </button>
      </div>
    </div>
  );
}
