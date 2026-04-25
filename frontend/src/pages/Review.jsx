import React, { useCallback, useEffect, useMemo, useState, lazy, Suspense } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, fileUrl } from "../lib/api";
import DocumentForm from "../components/DocumentForm";
import EmailDialog from "../components/EmailDialog";
import StatusBadge, { TypeBadge } from "../components/Badges";
import { useAuth, can } from "../lib/auth";
import { FloppyDisk, FileArrowDown, ArrowLeft, CheckCircle, PaperPlaneTilt, ArrowClockwise, Warning, CircleNotch } from "@phosphor-icons/react";

const TYPES = ["PO", "PR", "DO", "QUOTATION", "INVOICE", "OTHER"];

// Lazy loaded PDF iframe component with Intersection Observer
function LazyPDFViewer({ src, title }) {
  const [isVisible, setIsVisible] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const containerRef = React.useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasLoaded) {
          setIsVisible(true);
          setHasLoaded(true);
        }
      },
      { rootMargin: "200px" } // Start loading 200px before visible
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, [hasLoaded]);

  if (!isVisible) {
    return (
      <div ref={containerRef} className="w-full h-full flex items-center justify-center bg-[#1a1a1a]">
        <div className="text-[#71717A] text-sm flex items-center gap-2">
          <CircleNotch size={16} className="animate-spin" />
          Loading preview...
        </div>
      </div>
    );
  }

  return (
    <iframe
      src={src}
      title={title}
      className="w-full h-full"
      loading="lazy"
      referrerPolicy="no-referrer"
    />
  );
}

export default function Review() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [template, setTemplate] = useState(null);
  const [value, setValue] = useState({ header: {}, items: [], totals: {} });
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [typeOverride, setTypeOverride] = useState("");
  const [showEmail, setShowEmail] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState("");
  const { user } = useAuth();
  const nav = useNavigate();

  const loadTemplate = useCallback(async (docType) => {
    if (docType && docType !== "OTHER") {
      const tpl = await api.get(`/templates/${docType}`);
      setTemplate(tpl.data);
    } else {
      setTemplate(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const r = await api.get(`/documents/${id}`);
      if (cancelled) return;
      setDoc(r.data);
      setTypeOverride(r.data.type);
      setValue({
        header: r.data.extracted_data?.header || {},
        items: r.data.extracted_data?.items || [],
        totals: r.data.extracted_data?.totals || {},
      });
      await loadTemplate(r.data.type);
    })();
    return () => { cancelled = true; };
  }, [id, loadTemplate]);

  const onTypeChange = async (t) => {
    setTypeOverride(t);
    await loadTemplate(t);
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

  const retryExtraction = async () => {
    setRetrying(true);
    setRetryError("");
    try {
      const r = await api.post(`/documents/${id}/process`);
      setDoc(r.data);
      setValue({
        header: r.data.extracted_data?.header || {},
        items: r.data.extracted_data?.items || [],
        totals: r.data.extracted_data?.totals || {},
      });
      await loadTemplate(r.data.type);
    } catch (e) {
      setRetryError(e?.response?.data?.detail || e?.message || "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  const pdfSrc = useMemo(() => (doc?.source === "AUTO" ? fileUrl(doc.file_url) : null), [doc]);
  // Cache-bust the generated-PDF URL whenever the document is saved so the
  // browser/PDF viewer can't serve a stale render after a type or data change.
  const genPdf = `${process.env.REACT_APP_BACKEND_URL}/api/documents/${id}/pdf?v=${encodeURIComponent(doc?.updated_at || doc?.created_at || "")}`;

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
          {doc.extraction_provider && doc.extraction_provider !== "none" && (
            <span
              className="hidden md:inline text-[10px] uppercase tracking-[0.12em] font-semibold px-2 py-0.5 bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE]"
              title="The LLM provider that produced this extraction"
              data-testid="review-provider-badge"
            >
              {doc.extraction_provider}
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

      {(doc.extraction_error || doc.status === "FAILED") && (
        <div
          className="px-4 sm:px-8 py-3 bg-[#FEF2F2] border-b border-[#FECACA] flex flex-wrap items-start gap-3"
          data-testid="extraction-error-banner"
          role="alert"
        >
          <Warning size={18} weight="fill" className="text-[#DC2626] shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0 text-[12px] sm:text-[13px] text-[#991B1B] leading-snug">
            <div className="font-semibold mb-0.5">Extraction failed</div>
            <div className="text-[#7F1D1D]">
              {doc.extraction_error
                || "The LLM extraction step did not return a usable payload. Click Retry to try again."}
            </div>
            {retryError && (
              <div className="mt-1 text-[11px] text-[#B91C1C]" data-testid="extraction-retry-error">
                Retry error: {retryError}
              </div>
            )}
          </div>
          {can(user, "user") && (
            <button
              className="pf-btn pf-btn-secondary shrink-0"
              onClick={retryExtraction}
              disabled={retrying}
              data-testid="extraction-retry-btn"
              title="Re-run OCR & LLM extraction"
            >
              {retrying
                ? <CircleNotch size={14} className="animate-spin" />
                : <ArrowClockwise size={14} />}
              {retrying ? "Retrying…" : "Retry extraction"}
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] flex-1 overflow-hidden">
        <div className="hidden xl:block bg-[#27272A] border-r border-[#E5E7EB] overflow-hidden" data-testid="pdf-viewer-panel">
          {pdfSrc ? (
            <Suspense fallback={
              <div className="w-full h-full flex items-center justify-center bg-[#27272A]">
                <div className="text-[#71717A] text-sm flex items-center gap-2">
                  <CircleNotch size={16} className="animate-spin" />
                  Loading PDF...
                </div>
              </div>
            }>
              <LazyPDFViewer src={pdfSrc} title="PDF" />
            </Suspense>
          ) : (
            <div className="h-full flex items-center justify-center text-[#A1A1AA] text-sm p-8 text-center">
              This is a manually-created document. <br /> Use "Generated PDF" to preview the rendered output.
              <div className="mt-4">
                <Link to="/create" className="pf-btn pf-btn-secondary">Create another</Link>
              </div>
            </div>
          )}
        </div>

        <div className="overflow-y-auto bg-white">
          {/* Compact PDF link bar — shown at every breakpoint < xl, where the
              inline iframe doesn't fit (or doesn't render on mobile Chrome). */}
          {pdfSrc && (
            <div className="xl:hidden bg-[#FAFAFA] border-b border-[#E5E7EB] px-4 sm:px-8 py-2.5 flex items-center gap-3" data-testid="pdf-mobile-card">
              <div className="w-8 h-8 bg-[#0A0A0B] flex items-center justify-center shrink-0">
                <FileArrowDown size={14} color="#fff" weight="bold" />
              </div>
              <div className="min-w-0 flex-1 leading-tight">
                <div className="text-[10px] uppercase tracking-[0.12em] text-[#71717A] font-medium">Original PDF</div>
                <div className="text-[12px] font-medium truncate">{doc.filename || "document.pdf"}</div>
              </div>
              <a href={pdfSrc} target="_blank" rel="noreferrer" className="pf-btn pf-btn-secondary !px-3 !py-1.5 !text-xs shrink-0" data-testid="pdf-mobile-open">
                Open
              </a>
            </div>
          )}

          <div className="p-4 sm:p-6 lg:p-8 max-w-[1100px] mx-auto w-full">
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
      </div>
      {showEmail && <EmailDialog docId={id} onClose={() => setShowEmail(false)} />}
    </div>
  );
}
