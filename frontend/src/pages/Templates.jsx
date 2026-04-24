import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  useEffect(() => { api.get("/templates").then(r => setTemplates(r.data.templates)); }, []);

  return (
    <div className="p-10 pf-fade-up" data-testid="templates-page">
      <div className="mb-8">
        <div className="pf-overline mb-2">Blueprints</div>
        <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Templates</h1>
        <p className="text-[13px] text-[#52525B] mt-2 max-w-xl">
          Each template drives both auto-extraction and manual creation forms. Schemas are declarative — extend them in <code className="text-[12px] bg-[#F4F4F5] px-1 py-0.5">services/templates.py</code>.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map((t) => (
          <div key={t.document_type} className="pf-surface p-6" data-testid={`template-${t.document_type}`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="pf-overline">{t.document_type}</div>
                <div className="font-display text-[20px] font-semibold">{t.label}</div>
              </div>
              <Link to="/create" className="pf-btn pf-btn-secondary">Create</Link>
            </div>

            <div className="pf-overline mb-2">Header fields ({t.schema.header_fields.length})</div>
            <div className="flex flex-wrap gap-1 mb-4">
              {t.schema.header_fields.map((f) => (
                <span key={f.key} className="text-[11px] px-2 py-0.5 bg-[#F4F4F5] border border-[#E5E7EB]">{f.label}</span>
              ))}
            </div>

            <div className="pf-overline mb-2">Line item columns</div>
            <div className="flex flex-wrap gap-1 mb-4">
              {t.schema.item_columns.map((c) => (
                <span key={c.key} className="text-[11px] px-2 py-0.5 bg-[#F4F4F5] border border-[#E5E7EB]">{c.label}</span>
              ))}
            </div>

            <div className="pf-overline mb-2">Totals</div>
            <div className="flex flex-wrap gap-1">
              {t.schema.totals.length ? t.schema.totals.map((x) => (
                <span key={x.key} className="text-[11px] px-2 py-0.5 bg-[#F4F4F5] border border-[#E5E7EB]">{x.label}</span>
              )) : <span className="text-[11px] text-[#71717A]">None</span>}
              {t.schema.tax_rate > 0 && <span className="text-[11px] ml-2 text-[#52525B]">Tax rate: {(t.schema.tax_rate * 100).toFixed(0)}%</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
