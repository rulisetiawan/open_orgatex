import React, { useState, useEffect } from 'react';
import { Calculator, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../../services/api';

/**
 * Reusable live preview panel inside "Tambah Batch Baru" modals (BatchListView & KanbanView).
 * Calls POST /api/formulas/preview-program (debounced 250ms) whenever program_no, machine_no,
 * or batch inputs change, and displays all auto-calculated step parameters.
 */
export default function BatchFormulaPreview({ form }) {
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    if (!form?.program_no) {
      setPreview(null);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.post('/formulas/preview-program', {
          program_no: Number(form.program_no) || 1,
          machine_no: form.machine_no || null,
          batch_context: {
            fabric_weight_kg: Number(form.fabric_weight_kg) || 0,
            liquor_ratio: Number(form.liquor_ratio) || 0,
            fabric_length: Number(form.fabric_length) || 200,
            fabric_type: form.fabric_type || '',
            color_shade: form.color_shade || '',
            fabric_gsm: Number(form.fabric_gsm) || 180,
            dye_type: form.dye_type || '',
            chamber_count: Number(form.chamber_count) || 1,
            redye: Number(form.redye) || 0,
            article: form.article || '',
            color_name: form.color_name || '',
            color_code: form.color_code || '',
            customer: form.customer || '',
          },
        });
        if (!cancelled) {
          setPreview(res.data || null);
        }
      } catch {
        if (!cancelled) setPreview(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [
    form?.program_no,
    form?.machine_no,
    form?.fabric_weight_kg,
    form?.liquor_ratio,
    form?.fabric_length,
    form?.fabric_type,
    form?.color_shade,
    form?.fabric_gsm,
    form?.dye_type,
    form?.chamber_count,
    form?.redye,
    form?.article,
    form?.color_name,
    form?.color_code,
    form?.customer,
  ]);

  if (!loading && (!preview || !preview.has_formulas)) {
    return null;
  }

  const items = preview?.resolved_items || [];

  return (
    <div className="rounded-lg border border-indigo-300 dark:border-indigo-700/70 bg-indigo-50/60 dark:bg-indigo-950/25 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-800 dark:text-indigo-300">
          <Calculator className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          <span>Preview Parameter Otomatis (Formula fx)</span>
          {items.length > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-indigo-600 text-white font-mono">
              {items.length} param
            </span>
          )}
        </div>
        {loading && (
          <span className="text-[10px] text-indigo-600 dark:text-indigo-400 flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Menghitung...
          </span>
        )}
      </div>

      {items.length > 0 && (
        <div className="max-h-40 overflow-y-auto rounded border border-indigo-200 dark:border-indigo-800/60 bg-white dark:bg-boxdark divide-y divide-stroke dark:divide-strokedark">
          {items.map((it, idx) => (
            <div key={idx} className="px-2.5 py-1.5 flex items-center justify-between gap-2 text-[11px]">
              <div className="min-w-0">
                <div className="font-bold text-black dark:text-white truncate">
                  Step {it.step_no} · {it.function_name} (P{it.param_slot})
                </div>
                <div className="text-[10px] text-gray-500 dark:text-gray-400 truncate">
                  fx: <span className="font-semibold text-indigo-600 dark:text-indigo-400">{it.formula_name}</span>
                  {it.matched_label ? ` · ${it.matched_label}` : ''}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="font-mono font-black text-emerald-700 dark:text-emerald-400 text-xs flex items-center gap-1 justify-end">
                  {it.error ? (
                    <AlertTriangle className="h-3 w-3 text-rose-500" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                  )}
                  <span>
                    {it.computed_value} {it.unit}
                  </span>
                </div>
                {it.clamped && (
                  <span className="text-[9px] text-amber-600 font-semibold">Dibatasi Min/Maks</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
