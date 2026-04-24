import React, { useMemo } from "react";
import { Trash, Plus } from "@phosphor-icons/react";

/**
 * Generic schema-driven form for PO / PR / DO / QUOTATION.
 * Props:
 *   template: template schema object from API
 *   value: { header, items, totals }
 *   onChange: (next) => void
 */
export default function DocumentForm({ template, value, onChange }) {
  const headerFields = template?.schema?.header_fields || [];
  const itemCols = template?.schema?.item_columns || [];
  const totalsCfg = template?.schema?.totals || [];
  const taxRate = template?.schema?.tax_rate || 0;

  const header = value?.header || {};
  const items = value?.items || [];
  const totals = value?.totals || {};

  const computeTotals = (newItems) => {
    const amountKey = itemCols.find((c) => c.computed)?.key;
    let subtotal = 0;
    newItems.forEach((it) => {
      if (amountKey) {
        const comp = itemCols.find((c) => c.key === amountKey);
        const [a, b] = comp.computed.split("*");
        const n = Number(it[a] || 0) * Number(it[b] || 0);
        it[amountKey] = Number.isFinite(n) ? Number(n.toFixed(2)) : 0;
      }
      const val = Number(it[amountKey] || 0);
      subtotal += Number.isFinite(val) ? val : 0;
    });
    const tax = Number((subtotal * taxRate).toFixed(2));
    const grand_total = Number((subtotal + tax).toFixed(2));
    const next = { ...totals, subtotal: Number(subtotal.toFixed(2)) };
    if (totalsCfg.find((t) => t.key === "tax")) next.tax = tax;
    if (totalsCfg.find((t) => t.key === "grand_total")) next.grand_total = grand_total;
    return { items: newItems, totals: next };
  };

  const updateHeader = (k, v) => onChange({ ...value, header: { ...header, [k]: v } });

  const updateItem = (idx, k, v) => {
    const next = items.map((it, i) => (i === idx ? { ...it, [k]: v } : { ...it }));
    const rec = computeTotals(next);
    onChange({ ...value, items: rec.items, totals: rec.totals });
  };

  const addItem = () => {
    const blank = Object.fromEntries(itemCols.map((c) => [c.key, c.type === "number" ? 0 : ""]));
    const rec = computeTotals([...items.map((x) => ({ ...x })), blank]);
    onChange({ ...value, items: rec.items, totals: rec.totals });
  };

  const removeItem = (idx) => {
    const rec = computeTotals(items.filter((_, i) => i !== idx).map((x) => ({ ...x })));
    onChange({ ...value, items: rec.items, totals: rec.totals });
  };

  const amountKey = useMemo(() => itemCols.find((c) => c.computed)?.key, [itemCols]);

  return (
    <div className="space-y-8" data-testid="document-form">
      <section>
        <div className="pf-overline mb-3">Header</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {headerFields.map((f) => (
            <label key={f.key} className="block">
              <div className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] mb-1.5 font-medium">
                {f.label}{f.required && <span className="text-[#B91C1C] ml-1">*</span>}
              </div>
              {f.type === "textarea" ? (
                <textarea
                  className="pf-input"
                  rows={2}
                  value={header[f.key] ?? ""}
                  onChange={(e) => updateHeader(f.key, e.target.value)}
                  data-testid={`field-${f.key}`}
                />
              ) : (
                <input
                  className="pf-input"
                  type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"}
                  value={header[f.key] ?? ""}
                  onChange={(e) => updateHeader(f.key, e.target.value)}
                  data-testid={`field-${f.key}`}
                />
              )}
            </label>
          ))}
        </div>
      </section>

      {itemCols.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <div className="pf-overline">Line items</div>
            <button className="pf-btn pf-btn-secondary" onClick={addItem} data-testid="add-item-btn">
              <Plus size={13} weight="bold" /> Add row
            </button>
          </div>
          <div className="border border-[#E5E7EB]">
            <table className="pf-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  {itemCols.map((c) => <th key={c.key}>{c.label}</th>)}
                  <th style={{ width: 40 }} />
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr><td colSpan={itemCols.length + 2} className="text-center text-[#71717A] py-6">No items. Add a row.</td></tr>
                )}
                {items.map((it, idx) => (
                  <tr key={idx} data-testid={`item-row-${idx}`}>
                    <td className="tabular-nums text-[#71717A]">{idx + 1}</td>
                    {itemCols.map((c) => (
                      <td key={c.key}>
                        {c.type === "textarea" ? (
                          <textarea
                            className="pf-input"
                            rows={2}
                            value={it[c.key] ?? ""}
                            onChange={(e) => updateItem(idx, c.key, e.target.value)}
                            data-testid={`item-${idx}-${c.key}`}
                            disabled={c.computed === amountKey ? false : false}
                          />
                        ) : (
                          <input
                            className="pf-input"
                            type={c.type === "number" ? "number" : "text"}
                            value={it[c.key] ?? ""}
                            onChange={(e) => updateItem(idx, c.key, c.type === "number" ? e.target.value : e.target.value)}
                            readOnly={c.key === amountKey}
                            data-testid={`item-${idx}-${c.key}`}
                          />
                        )}
                      </td>
                    ))}
                    <td>
                      <button className="pf-btn pf-btn-ghost" onClick={() => removeItem(idx)} data-testid={`remove-item-${idx}`}>
                        <Trash size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {totalsCfg.length > 0 && (
        <section>
          <div className="pf-overline mb-3">Totals</div>
          <div className="ml-auto max-w-md border border-[#E5E7EB]">
            {totalsCfg.map((t) => (
              <div key={t.key} className="flex justify-between px-4 py-2 border-b border-[#F4F4F5] last:border-0">
                <div className="text-[13px] text-[#52525B]">{t.label}</div>
                <div className="tabular-nums text-[13px] font-medium">
                  {totals?.[t.key] != null ? Number(totals[t.key]).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
