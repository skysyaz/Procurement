import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorText } from "../lib/api";
import { Plus, Trash, ArrowCounterClockwise, FloppyDisk, PencilSimple } from "@phosphor-icons/react";

const FIELD_TYPES = ["text", "textarea", "number", "date"];
const BUILTIN = new Set(["PO", "PR", "DO", "QUOTATION", "INVOICE"]);

export default function AdminTemplates() {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(null); // copy of selected template for editing
  const [showNew, setShowNew] = useState(false);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(null);

  const load = async () => {
    try {
      const r = await api.get("/templates");
      setTemplates(r.data.templates);
      if (selected) {
        const fresh = r.data.templates.find((t) => t.document_type === selected.document_type);
        setSelected(fresh || null);
      }
    } catch (e) { setErr(apiErrorText(e)); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const startEdit = (tpl) => {
    setSelected(tpl);
    setEditing(JSON.parse(JSON.stringify(tpl)));
    setSaved(null);
  };

  const save = async () => {
    try {
      await api.post("/admin/templates", editing);
      setSaved(editing.document_type);
      await load();
      setEditing(null);
    } catch (e) { alert(apiErrorText(e)); }
  };

  const reset = async (dtype) => {
    if (!window.confirm(`Reset ${dtype} to built-in defaults?`)) return;
    try {
      await api.delete(`/admin/templates/${dtype}`);
      setEditing(null); setSelected(null);
      await load();
    } catch (e) { alert(apiErrorText(e)); }
  };

  const remove = async (dtype) => {
    if (!window.confirm(`Delete custom template ${dtype}? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/templates/${dtype}`);
      setEditing(null); setSelected(null);
      await load();
    } catch (e) { alert(apiErrorText(e)); }
  };

  return (
    <div className="p-10 pf-fade-up" data-testid="admin-templates-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="pf-overline mb-2">Administration</div>
          <h1 className="font-display text-[32px] font-bold tracking-tight leading-none">Templates</h1>
          <p className="text-[13px] text-[#52525B] mt-2">Edit built-in schemas or define custom document types without touching code.</p>
        </div>
        <button className="pf-btn pf-btn-primary" onClick={() => setShowNew(true)} data-testid="new-template-btn">
          <Plus size={14} weight="bold" /> New template
        </button>
      </div>
      {err && <div className="text-[12px] text-[#B91C1C] mb-4">{err}</div>}
      {saved && <div className="text-[12px] text-[#047857] mb-4">Saved {saved}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="pf-surface" data-testid="template-list">
          <div className="px-5 py-3 border-b border-[#E5E7EB] pf-overline">Templates ({templates.length})</div>
          <ul>
            {templates.map((t) => (
              <li key={t.document_type}
                  className={"px-5 py-3 border-b border-[#F4F4F5] cursor-pointer flex items-center justify-between " + (selected?.document_type === t.document_type ? "bg-[#FAFAFA]" : "hover:bg-[#FAFAFA]")}
                  onClick={() => startEdit(t)} data-testid={`template-item-${t.document_type}`}>
                <div>
                  <div className="font-medium text-[14px]">{t.label}</div>
                  <div className="text-[11px] text-[#71717A] font-mono-tab">{t.document_type} · {t.schema.header_fields.length} fields · {t.schema.item_columns.length} cols</div>
                </div>
                <span className={"pf-badge " + (BUILTIN.has(t.document_type) ? "pf-badge-neutral" : "pf-badge-info")}>
                  {BUILTIN.has(t.document_type) ? "Built-in" : "Custom"}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="lg:col-span-2">
          {editing ? (
            <Editor editing={editing} setEditing={setEditing} onSave={save}
                    onReset={() => reset(editing.document_type)}
                    onRemove={() => remove(editing.document_type)}
                    isBuiltin={BUILTIN.has(editing.document_type)} />
          ) : (
            <div className="pf-surface p-10 text-center text-[#71717A] text-[13px]">
              <PencilSimple size={28} className="mx-auto mb-3 text-[#A1A1AA]" />
              Select a template on the left to edit, or create a new one.
            </div>
          )}
        </div>
      </div>

      {showNew && (
        <NewTemplateDialog
          onClose={() => setShowNew(false)}
          onCreated={async (tpl) => { setShowNew(false); await load(); startEdit(tpl); }}
        />
      )}
    </div>
  );
}

function Editor({ editing, setEditing, onSave, onReset, onRemove, isBuiltin }) {
  const updateField = (listKey, idx, key, value) => {
    const next = { ...editing, schema: { ...editing.schema, [listKey]: editing.schema[listKey].map((x, i) => i === idx ? { ...x, [key]: value } : x) } };
    setEditing(next);
  };
  const addRow = (listKey, blank) => setEditing({ ...editing, schema: { ...editing.schema, [listKey]: [...editing.schema[listKey], blank] } });
  const removeRow = (listKey, idx) => setEditing({ ...editing, schema: { ...editing.schema, [listKey]: editing.schema[listKey].filter((_, i) => i !== idx) } });

  return (
    <div className="pf-surface p-6 space-y-6" data-testid="template-editor">
      <div className="flex items-center justify-between">
        <div>
          <div className="pf-overline">Editing</div>
          <div className="font-display text-[22px] font-semibold tracking-tight">
            {editing.label}
            <span className="ml-2 text-[12px] text-[#71717A] font-mono-tab">{editing.document_type}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {isBuiltin ? (
            <button className="pf-btn pf-btn-secondary" onClick={onReset} data-testid="reset-template">
              <ArrowCounterClockwise size={14} /> Reset to default
            </button>
          ) : (
            <button className="pf-btn pf-btn-danger" onClick={onRemove} data-testid="delete-template">
              <Trash size={14} /> Delete
            </button>
          )}
          <button className="pf-btn pf-btn-primary" onClick={onSave} data-testid="save-template">
            <FloppyDisk size={14} /> Save changes
          </button>
        </div>
      </div>

      <div>
        <label className="block text-[11px] uppercase tracking-[0.12em] text-[#71717A] font-medium mb-1.5">Label</label>
        <input className="pf-input max-w-sm" value={editing.label} onChange={(e) => setEditing({ ...editing, label: e.target.value })} data-testid="edit-label" />
      </div>

      <FieldEditor title="Header fields" rows={editing.schema.header_fields}
        add={() => addRow("header_fields", { key: "new_field", label: "New Field", type: "text" })}
        update={(i, k, v) => updateField("header_fields", i, k, v)}
        remove={(i) => removeRow("header_fields", i)}
        showRequired testIdPrefix="h" />

      <FieldEditor title="Line item columns" rows={editing.schema.item_columns}
        add={() => addRow("item_columns", { key: "new_col", label: "New Column", type: "text" })}
        update={(i, k, v) => updateField("item_columns", i, k, v)}
        remove={(i) => removeRow("item_columns", i)}
        showComputed testIdPrefix="c" />

      <FieldEditor title="Totals" rows={editing.schema.totals}
        add={() => addRow("totals", { key: "new_total", label: "New Total" })}
        update={(i, k, v) => updateField("totals", i, k, v)}
        remove={(i) => removeRow("totals", i)}
        minimal testIdPrefix="t" />

      <div>
        <label className="block text-[11px] uppercase tracking-[0.12em] text-[#71717A] font-medium mb-1.5">Tax rate (decimal, e.g. 0.08)</label>
        <input className="pf-input max-w-[140px]" type="number" step="0.01" value={editing.schema.tax_rate ?? 0}
          onChange={(e) => setEditing({ ...editing, schema: { ...editing.schema, tax_rate: parseFloat(e.target.value) || 0 } })} data-testid="edit-tax-rate" />
      </div>
    </div>
  );
}

function FieldEditor({ title, rows, add, update, remove, showRequired, showComputed, minimal, testIdPrefix }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="pf-overline">{title} ({rows.length})</div>
        <button className="pf-btn pf-btn-secondary" onClick={add} data-testid={`add-${testIdPrefix}`}>
          <Plus size={13} /> Add
        </button>
      </div>
      <div className="border border-[#E5E7EB]">
        <table className="pf-table">
          <thead>
            <tr>
              <th style={{ width: 36 }}>#</th>
              <th>Key</th>
              <th>Label</th>
              {!minimal && <th>Type</th>}
              {showRequired && <th>Required</th>}
              {showComputed && <th>Computed (e.g. qty*unit_rate)</th>}
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={8} className="text-center text-[#71717A] py-4">Empty.</td></tr>}
            {rows.map((f, i) => (
              <tr key={i}>
                <td className="tabular-nums text-[#71717A]">{i + 1}</td>
                <td><input className="pf-input font-mono-tab text-[12px]" value={f.key || ""} onChange={(e) => update(i, "key", e.target.value)} data-testid={`${testIdPrefix}-key-${i}`} /></td>
                <td><input className="pf-input" value={f.label || ""} onChange={(e) => update(i, "label", e.target.value)} data-testid={`${testIdPrefix}-label-${i}`} /></td>
                {!minimal && (
                  <td>
                    <select className="pf-input" value={f.type || "text"} onChange={(e) => update(i, "type", e.target.value)} data-testid={`${testIdPrefix}-type-${i}`}>
                      {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </td>
                )}
                {showRequired && (
                  <td><input type="checkbox" checked={!!f.required} onChange={(e) => update(i, "required", e.target.checked)} data-testid={`${testIdPrefix}-req-${i}`} /></td>
                )}
                {showComputed && (
                  <td><input className="pf-input font-mono-tab text-[12px]" placeholder="quantity*unit_rate" value={f.computed || ""} onChange={(e) => update(i, "computed", e.target.value)} data-testid={`${testIdPrefix}-comp-${i}`} /></td>
                )}
                <td>
                  <button className="pf-btn pf-btn-ghost" onClick={() => remove(i)} data-testid={`${testIdPrefix}-del-${i}`}><Trash size={13} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NewTemplateDialog({ onClose, onCreated }) {
  const [docType, setDocType] = useState("");
  const [label, setLabel] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const r = await api.post("/admin/templates", {
        document_type: docType.toUpperCase().replace(/[^A-Z0-9_]/g, "_"),
        label: label.trim() || docType,
        schema: {
          header_fields: [{ key: "reference", label: "Reference", type: "text", required: true }],
          item_columns: [{ key: "description", label: "Description", type: "textarea" }],
          totals: [],
          tax_rate: 0,
        },
      });
      onCreated(r.data);
    } catch (ex) {
      setErr(apiErrorText(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-[#0A0A0B]/40 z-50 flex items-center justify-center p-4" data-testid="new-template-dialog">
      <form onSubmit={submit} className="pf-surface p-8 w-full max-w-md bg-white">
        <div className="pf-overline mb-2">New</div>
        <h2 className="font-display text-[22px] font-semibold tracking-tight">Create template</h2>
        <p className="text-[12px] text-[#52525B] mt-1">You can refine header fields, item columns, and totals after creating.</p>
        <div className="mt-6 space-y-4">
          <label className="block">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Document type (A-Z, 0-9, _)</div>
            <input className="pf-input font-mono-tab" value={docType} onChange={(e) => setDocType(e.target.value.toUpperCase())} required data-testid="new-doctype" />
          </label>
          <label className="block">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">Label</div>
            <input className="pf-input" value={label} onChange={(e) => setLabel(e.target.value)} data-testid="new-label" />
          </label>
          {err && <div className="text-[12px] text-[#B91C1C]">{err}</div>}
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button type="button" className="pf-btn pf-btn-secondary" onClick={onClose}>Cancel</button>
          <button className="pf-btn pf-btn-primary" disabled={busy} data-testid="create-template-submit">
            <Plus size={14} weight="bold" /> Create
          </button>
        </div>
      </form>
    </div>
  );
}
