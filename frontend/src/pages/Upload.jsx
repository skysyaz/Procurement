import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { UploadSimple, FilePdf, CircleNotch, CheckCircle } from "@phosphor-icons/react";

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [stage, setStage] = useState("idle"); // idle|uploading|processing|done|error
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
    setError("");
    setStage("uploading");
    setProgress("Uploading PDF to storage…");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await api.post("/documents/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const id = up.data.id;
      setStage("processing");
      setProgress("Running OCR + classification + extraction…");
      await api.post(`/documents/${id}/process`);
      setStage("done");
      setProgress("Complete. Redirecting to review…");
      setTimeout(() => nav(`/review/${id}`), 600);
    } catch (err) {
      setStage("error");
      setError(err?.response?.data?.detail || err.message || "Failed");
    }
  };

  return (
    <div className="p-10 pf-fade-up" data-testid="upload-page">
      <div className="mb-8">
        <div className="pf-overline mb-2">Auto mode</div>
        <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Upload & Extract</h1>
        <p className="text-[13px] text-[#52525B] mt-2 max-w-xl">
          Drop a procurement PDF — POs, quotations, delivery orders or invoices. The pipeline will classify the document and map its contents to the appropriate schema.
        </p>
      </div>

      <div
        className="pf-surface pf-grid-bg relative overflow-hidden"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        data-testid="upload-dropzone"
      >
        <div className="p-16 flex flex-col items-center text-center">
          <div className="w-14 h-14 bg-[#0A0A0B] flex items-center justify-center mb-5">
            <UploadSimple size={24} color="#fff" weight="bold" />
          </div>
          <div className="font-display text-[22px] font-semibold tracking-tight">Drop a PDF, or choose a file</div>
          <div className="text-[12px] text-[#52525B] mt-1.5">Supports PO, PR, DO, Quotation and Invoice documents</div>
          <label className="pf-btn pf-btn-primary mt-6 cursor-pointer" data-testid="upload-choose-btn">
            <input
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              data-testid="upload-file-input"
            />
            <FilePdf size={14} weight="bold" /> Choose file
          </label>
          {file && (
            <div className="mt-6 flex items-center gap-3 bg-[#F4F4F5] px-4 py-2 text-[13px]" data-testid="selected-file">
              <FilePdf size={14} />
              <span className="font-medium">{file.name}</span>
              <span className="text-[#71717A] tabular-nums">{(file.size / 1024).toFixed(1)} KB</span>
            </div>
          )}
          <button
            className="pf-btn pf-btn-primary mt-4"
            disabled={!file || stage === "uploading" || stage === "processing"}
            onClick={run}
            data-testid="upload-process-btn"
          >
            {stage === "uploading" || stage === "processing" ? (
              <><CircleNotch size={14} className="animate-spin" /> Processing…</>
            ) : stage === "done" ? (
              <><CheckCircle size={14} weight="bold" /> Done</>
            ) : (
              <>Run OCR & Extract</>
            )}
          </button>
          {progress && (
            <div className="mt-4 text-[12px] text-[#52525B] pf-pulse" data-testid="upload-progress-text">{progress}</div>
          )}
          {error && <div className="mt-4 text-[12px] text-[#B91C1C]" data-testid="upload-error">{error}</div>}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-0 mt-6 pf-surface">
        {["Upload", "OCR", "Classify", "Extract"].map((s, i) => (
          <div key={s} className={"p-5 " + (i < 3 ? "border-r border-[#E5E7EB]" : "")}>
            <div className="pf-overline">Step {i + 1}</div>
            <div className="font-display text-[16px] font-semibold mt-1">{s}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
