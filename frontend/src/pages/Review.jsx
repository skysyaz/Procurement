import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, fileUrl } from "../lib/api";
import DocumentForm from "../components/DocumentForm";
import EmailDialog from "../components/EmailDialog";
import StatusBadge, { TypeBadge } from "../components/Badges";
import { useAuth, can } from "../lib/auth";
import { FloppyDisk, FileArrowDown, ArrowLeft, CheckCircle, PaperPlaneTilt } from "@phosphor-icons/react";

const TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];

export default function Review() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [template, setTemplate] = useState(null);
  const [value, setValue] = useState({ header: {}, items: [], totals: {} });
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [typeOverride, setTypeOverride] = useState("");
  const [showEmail, setShowEmail] = useState(false);
  const { user } = useAuth();
  const nav = useNavigate();

  const loadAll = async (docType) => {
    if (docType && docType !== "OTHER") {
      const tpl = await api.get(`/templates/${docType}`);
      setTemplate(tpl.data);
    } else {
      setTemplate(null);
    }
  };

  useEffect(() => {
    (async () => {
      const r = await api.get(`/documents/${id}`);
      setDoc(r.data);
      setTypeOverride(r.data.type);
      setValue({
        header: r.data.extracted_data?.header || {},
        items: r.data.extracted_data?.items || [],
        totals: r.data.extracted_data?.totals || {},
      });
      await loadAll(r.data.type);
    })();
  }, [id]);

  const onTypeChange = async (t) => {
    setTypeOverride(t);
    await loadAll(t);
  };

  const save = async (markAs) => {
    setSaving(true);
    try {
      const r = await api.put(`/documents/${id}/review`, {
        extracted_data: value,
        status: markAs || "REVIEWED",
        type: typeOverride,
      });
      setDoc(r.data);
      setSavedAt(new Date().toLocaleTimeString());
    } finally {
      setSaving(false);
    }
  };

  const pdfSrc = useMemo(() => (doc?.source === "AUTO" ? fileUrl(doc.file_url) : null), [doc]);
  const genPdf = `${process.env.REACT_APP_BACKEND_URL}/api/documents/${id}/pdf`;

  if (!doc) return <div className="p-10 pf-pulse text-[#71717A]">Loading…</div>;

  return (
    <div className="h-screen flex flex-col" data-testid="review-page">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E5E7EB] px-4 sm:px-8 py-3 bg-white">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 min-w-0">
          <button className="pf-btn pf-btn-ghost" onClick={() => nav(-1)} data-testid="review-back">
            <ArrowLeft size={14} /> Back
          </button>
          <div className="hidden sm:block h-6 w-px bg-[#E5E7EB]" />
          <TypeBadge type={doc.type} />
          <div className="font-display text-[14px] sm:text-[18px] font-semibold tracking-tight truncate max-w-[160px] sm:max-w-none">
            {doc.filename || `${doc.type} draft`}
          </div>
          <StatusBadge status={doc.status} />
          {doc.confidence_score > 0 && (
            <span className="hidden sm:inline text-[11px] text-[#71717A] tabular-nums">
              Confidence: {Math.round(doc.confidence_score * 100)}% · {doc.classification_method}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="pf-input w-[120px] sm:w-[150px]"
            value={typeOverride}
            onChange={(e) => onTypeChange(e.target.value)}
            data-testid="review-type-select"
          >
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <a href={genPdf} target="_blank" rel="noreferrer" className="pf-btn pf-btn-secondary" data-testid="review-download-pdf">
            <FileArrowDown size={14} /> Generated PDF
          </a>
          {can(user, "manager") && (
            <button className="pf-btn pf-btn-secondary" onClick={() => setShowEmail(true)} data-testid="review-email-btn">
              <PaperPlaneTilt size={14} /> Email
            </button>
          )}
          {can(user, "user") && (
            <button className="pf-btn pf-btn-secondary" disabled={saving} onClick={() => save("REVIEWED")} data-testid="review-save-btn">
              <FloppyDisk size={14} /> {saving ? "Saving…" : "Save draft"}
            </button>
          )}
          {can(user, "manager") && (
            <button className="pf-btn pf-btn-primary" disabled={saving} onClick={() => save("FINAL")} data-testid="review-finalize-btn">
              <CheckCircle size={14} weight="bold" /> Finalize
            </button>
          )}
        </div>
      </div>
      {savedAt && <div className="px-8 py-1 text-[11px] text-[#047857] bg-[#ECFDF5] border-b border-[#D1FAE5]">Saved at {savedAt}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 flex-1 overflow-hidden">
        <div className="hidden lg:block bg-[#27272A] border-r border-[#E5E7EB] overflow-hidden" data-testid="pdf-viewer-panel">
          {pdfSrc ? (
            <iframe src={pdfSrc} title="PDF" className="w-full h-full" />
          ) : (
            <div className="h-full flex items-center justify-center text-[#A1A1AA] text-sm p-8 text-center">
              This is a manually-created document. <br /> Use "Generated PDF" to preview the rendered output.
              <div className="mt-4">
                <Link to="/create" className="pf-btn pf-btn-secondary">Create another</Link>
              </div>
            </div>
          )}
        </div>

        {/* Mobile PDF card — iframe PDF preview doesn't work reliably on mobile browsers */}
        {pdfSrc && (
          <div className="lg:hidden bg-[#FAFAFA] border-b border-[#E5E7EB] p-4 flex items-center gap-3" data-testid="pdf-mobile-card">
            <div className="w-10 h-10 bg-[#0A0A0B] flex items-center justify-center shrink-0">
              <FileArrowDown size={18} color="#fff" weight="bold" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] font-medium">Original PDF</div>
              <div className="text-[13px] font-medium truncate">{doc.filename || "document.pdf"}</div>
            </div>
            <a href={pdfSrc} target="_blank" rel="noreferrer" className="pf-btn pf-btn-secondary" data-testid="pdf-mobile-open">
              Open
            </a>
          </div>
        )}

        <div className="overflow-y-auto bg-white p-4 sm:p-8">
          {template ? (
            <DocumentForm template={template} value={value} onChange={setValue} />
          ) : (
            <div className="text-[#71717A] text-[13px]">
              Document classified as <b>{doc.type}</b>. Select a specific type above to map it to a structured template.
              <div className="mt-6">
                <div className="pf-overline mb-2">Raw OCR text</div>
                <pre className="text-[11px] whitespace-pre-wrap bg-[#FAFAFA] p-4 border border-[#E5E7EB] max-h-[400px] overflow-auto">{doc.raw_text || "(no text extracted)"}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
      {showEmail && <EmailDialog docId={id} onClose={() => setShowEmail(false)} />}
    </div>
  );
}
