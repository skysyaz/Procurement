import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorText } from "../lib/api";
import { UploadSimple, FilePdf, CircleNotch, CheckCircle, StackSimple, FileArrowUp } from "@phosphor-icons/react";

export default function UploadPage() {
  const [mode, setMode] = useState("single"); // single | bulk
  return (
    <div className="p-10 pf-fade-up" data-testid="upload-page">
      <div className="mb-8">
        <div className="pf-overline mb-2">Auto mode</div>
        <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Upload & Extract</h1>
        <p className="text-[13px] text-[#52525B] mt-2 max-w-xl">
          Drop procurement PDFs — POs, quotations, delivery orders, invoices, purchase requests. Pipeline auto-classifies and extracts fields.
        </p>
      </div>

      <div className="flex gap-2 mb-6">
        <button className={"pf-btn " + (mode === "single" ? "pf-btn-primary" : "pf-btn-secondary")} onClick={() => setMode("single")} data-testid="mode-single">
          <FileArrowUp size={14} /> Single document
        </button>
        <button className={"pf-btn " + (mode === "bulk" ? "pf-btn-primary" : "pf-btn-secondary")} onClick={() => setMode("bulk")} data-testid="mode-bulk">
          <StackSimple size={14} /> Bulk upload (up to 20)
        </button>
      </div>

      {mode === "single" ? <SingleUpload /> : <BulkUpload />}
    </div>
  );
}

function SingleUpload() {
  const [file, setFile] = useState(null);
  const [stage, setStage] = useState("idle");
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const run = async () => {
    if (!file) return;
    setError(""); setStage("uploading"); setProgress("Uploading PDF…");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await api.post("/documents/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const id = up.data.id;
      setStage("processing"); setProgress("OCR + classification + extraction…");
      await api.post(`/documents/${id}/process`);
      setStage("done"); setProgress("Complete.");
      setTimeout(() => nav(`/review/${id}`), 500);
    } catch (err) {
      setStage("error"); setError(apiErrorText(err));
    }
  };

  return (
    <div className="pf-surface pf-grid-bg relative overflow-hidden" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()} data-testid="upload-dropzone">
      <div className="p-16 flex flex-col items-center text-center">
        <div className="w-14 h-14 bg-[#0A0A0B] flex items-center justify-center mb-5">
          <UploadSimple size={24} color="#fff" weight="bold" />
        </div>
        <div className="font-display text-[22px] font-semibold tracking-tight">Drop a PDF, or choose a file</div>
        <div className="text-[12px] text-[#52525B] mt-1.5">Digital or scanned — Tesseract handles image-only PDFs.</div>
        <label className="pf-btn pf-btn-primary mt-6 cursor-pointer" data-testid="upload-choose-btn">
          <input type="file" accept="application/pdf" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="upload-file-input" />
          <FilePdf size={14} weight="bold" /> Choose file
        </label>
        {file && (
          <div className="mt-6 flex items-center gap-3 bg-[#F4F4F5] px-4 py-2 text-[13px]" data-testid="selected-file">
            <FilePdf size={14} />
            <span className="font-medium">{file.name}</span>
            <span className="text-[#71717A] tabular-nums">{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        )}
        <button className="pf-btn pf-btn-primary mt-4" disabled={!file || stage === "uploading" || stage === "processing"} onClick={run} data-testid="upload-process-btn">
          {stage === "uploading" || stage === "processing" ? (
            <><CircleNotch size={14} className="animate-spin" /> Processing…</>
          ) : stage === "done" ? (
            <><CheckCircle size={14} weight="bold" /> Done</>
          ) : (
            <>Run OCR & Extract</>
          )}
        </button>
        {progress && <div className="mt-4 text-[12px] text-[#52525B] pf-pulse" data-testid="upload-progress-text">{progress}</div>}
        {error && <div className="mt-4 text-[12px] text-[#B91C1C]" data-testid="upload-error">{error}</div>}
      </div>
    </div>
  );
}

function BulkUpload() {
  const [files, setFiles] = useState([]);
  const [queued, setQueued] = useState([]);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");

  const start = async () => {
    if (!files.length) return;
    setError("");
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    try {
      const r = await api.post("/documents/bulk-upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setQueued(r.data.items);
      setPolling(true);
    } catch (e) { setError(apiErrorText(e)); }
  };

  useEffect(() => {
    if (!polling || queued.length === 0) return;
    const ids = queued.map((q) => q.id).filter(Boolean).join(",");
    if (!ids) return;
    const iv = setInterval(async () => {
      try {
        const r = await api.get(`/documents/bulk-status?ids=${ids}`);
        setQueued((cur) => cur.map((q) => r.data.find((x) => x.id === q.id) || q));
        const allDone = r.data.every((x) => x.status === "EXTRACTED" || x.status === "FAILED");
        if (allDone) setPolling(false);
      } catch (err) {
        console.warn("Bulk status poll failed:", err?.message || err);
      }
    }, 2000);
    return () => clearInterval(iv);
    // Only re-run when polling flips on/off or the queued id-set changes — not
    // on every status update, which would cause an infinite re-subscribe loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polling, queued.map((q) => q.id).join(",")]);

  return (
    <div className="pf-surface p-8" data-testid="bulk-dropzone">
      <input
        type="file" multiple accept="application/pdf"
        onChange={(e) => setFiles(e.target.files)}
        className="block w-full border border-dashed border-[#D4D4D8] p-6 text-[13px]"
        data-testid="bulk-files"
      />
      <div className="mt-4 flex items-center justify-between">
        <div className="text-[12px] text-[#52525B]">
          {files.length ? `${files.length} file(s) selected` : "Select up to 20 PDFs"}
        </div>
        <button className="pf-btn pf-btn-primary" disabled={!files.length} onClick={start} data-testid="bulk-submit">
          <UploadSimple size={14} /> Queue for processing
        </button>
      </div>
      {error && <div className="mt-3 text-[12px] text-[#B91C1C]">{error}</div>}

      {queued.length > 0 && (
        <div className="mt-6 border border-[#E5E7EB]">
          <table className="pf-table">
            <thead>
              <tr><th>#</th><th>Filename</th><th>Type</th><th>Status</th></tr>
            </thead>
            <tbody>
              {queued.map((q, i) => (
                <tr key={q.id || i} data-testid={`bulk-row-${i}`}>
                  <td className="tabular-nums text-[#71717A]">{i + 1}</td>
                  <td className="font-medium">{q.filename}</td>
                  <td>{q.type || "—"}</td>
                  <td>
                    <span className={"pf-badge " + (
                      q.status === "EXTRACTED" ? "pf-badge-ok" :
                      q.status === "FAILED" ? "pf-badge-err" :
                      q.status === "PROCESSING" ? "pf-badge-warn" : "pf-badge-info"
                    )}>
                      {q.status || (q.error ? "ERROR" : "QUEUED")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
