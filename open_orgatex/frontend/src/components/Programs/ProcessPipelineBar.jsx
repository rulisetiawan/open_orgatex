import React from 'react';
import {
  ChevronRight,
  Plus,
  Wand2,
  Copy,
  Trash2,
  ArrowLeft,
  ArrowRight,
  Flame,
  Clock,
  Boxes,
  Layers,
  ListTree,
  List
} from 'lucide-react';

const CATEGORY_STYLES = {
  Pretreatment: {
    badge: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-700',
    border: 'border-amber-400 dark:border-amber-600',
    bgActive: 'bg-amber-50/80 dark:bg-amber-950/30 ring-2 ring-amber-500'
  },
  Dyeing: {
    badge: 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-700',
    border: 'border-indigo-400 dark:border-indigo-600',
    bgActive: 'bg-indigo-50/80 dark:bg-indigo-950/30 ring-2 ring-indigo-500'
  },
  Washing: {
    badge: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-700',
    border: 'border-rose-400 dark:border-rose-600',
    bgActive: 'bg-rose-50/80 dark:bg-rose-950/30 ring-2 ring-rose-500'
  },
  Rinse: {
    badge: 'bg-cyan-100 text-cyan-800 border-cyan-300 dark:bg-cyan-950/50 dark:text-cyan-300 dark:border-cyan-700',
    border: 'border-cyan-400 dark:border-cyan-600',
    bgActive: 'bg-cyan-50/80 dark:bg-cyan-950/30 ring-2 ring-cyan-500'
  },
  Finishing: {
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-700',
    border: 'border-emerald-400 dark:border-emerald-600',
    bgActive: 'bg-emerald-50/80 dark:bg-emerald-950/30 ring-2 ring-emerald-500'
  },
  General: {
    badge: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    border: 'border-slate-400 dark:border-slate-600',
    bgActive: 'bg-slate-50/80 dark:bg-slate-800/40 ring-2 ring-slate-500'
  }
};

export default function ProcessPipelineBar({
  subPrograms = [],
  activeSubIdx = 0,
  onSelectSub,
  onMoveSub,
  onDuplicateSub,
  onDeleteSub,
  onOpenDrawer,
  onOpenWizard,
  isGroupedView = true,
  onToggleGroupedView
}) {
  return (
    <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark shadow-sm p-4 space-y-3">
      {/* Top Header & Quick Mode Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stroke dark:border-strokedark">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-black dark:text-white">
                Alur Proses & Sub-Program (Fasa Resep)
              </h3>
              <span className="text-[10px] bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 font-bold px-2 py-0.5 rounded border border-indigo-300 dark:border-indigo-800 font-mono">
                {subPrograms.length} Fasa Terangkai
              </span>
            </div>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Klik kotak fasa untuk fokus atau geser urutan modul proses pencelupan.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Toggle View Mode: Grouped Tree vs Flat Linear */}
          <div className="inline-flex rounded-lg border border-stroke dark:border-strokedark p-0.5 bg-gray-50 dark:bg-meta-4/40 text-xs">
            <button
              type="button"
              onClick={() => onToggleGroupedView && onToggleGroupedView(true)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-semibold transition ${
                isGroupedView
                  ? 'bg-white dark:bg-boxdark text-primary dark:text-white shadow-xs'
                  : 'text-gray-500 hover:text-black dark:hover:text-white'
              }`}
              title="Tampilkan langkah dikelompokkan per Sub-Program / Fasa"
            >
              <ListTree className="h-3.5 w-3.5" />
              <span>Grup Fasa</span>
            </button>
            <button
              type="button"
              onClick={() => onToggleGroupedView && onToggleGroupedView(false)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-semibold transition ${
                !isGroupedView
                  ? 'bg-white dark:bg-boxdark text-primary dark:text-white shadow-xs'
                  : 'text-gray-500 hover:text-black dark:hover:text-white'
              }`}
              title="Tampilkan semua langkah linier SECOM 01..N"
            >
              <List className="h-3.5 w-3.5" />
              <span>Linier Datar</span>
            </button>
          </div>
        </div>
      </div>

      {/* Horizontal Pipeline Sequence Cards */}
      <div className="flex items-center gap-2 overflow-x-auto py-2 px-1 no-scrollbar scroll-smooth">
        {subPrograms.length === 0 ? (
          <div className="w-full text-center py-6 text-gray-400 text-xs border-2 border-dashed border-stroke dark:border-strokedark rounded-xl">
            Belum ada fasa/sub-program terangkai.
          </div>
        ) : (
          subPrograms.map((sub, idx) => {
            const isSelected = idx === activeSubIdx;
            const catStyle = CATEGORY_STYLES[sub.category] || CATEGORY_STYLES.General;
            const stepsCount = sub.steps ? sub.steps.length : 0;
            
            // Calculate phase metrics
            let phaseTemp = sub.parameters?.temperature;
            let phaseTime = sub.parameters?.hold_time;
            if (!phaseTemp && sub.steps) {
              const temps = sub.steps
                .map(s => {
                  const f141 = s.functions?.find(f => f.function_id === 141);
                  return f141?.params?.[0] || s.summary_temp || 0;
                })
                .filter(t => t > 0);
              if (temps.length > 0) phaseTemp = Math.max(...temps);
            }
            if (!phaseTime && sub.steps) {
              phaseTime = sub.steps.reduce((acc, s) => acc + (s.summary_time_min || 0), 0);
            }

            return (
              <React.Fragment key={sub.id || `${sub.treatment_number || 'sub'}-${idx}`}>
                <div
                  onClick={() => onSelectSub && onSelectSub(idx)}
                  className={`group relative flex-shrink-0 w-60 rounded-xl border p-3 cursor-pointer transition-all duration-200 select-none ${
                    isSelected
                      ? `${catStyle.bgActive} shadow-md`
                      : 'border-stroke dark:border-strokedark bg-gray-50/70 dark:bg-meta-4/20 hover:bg-gray-100/90 dark:hover:bg-meta-4/50 hover:shadow-sm'
                  }`}
                >
                  {/* Card Header: Position & Category Badge */}
                  <div className="flex items-center justify-between gap-1.5 mb-1.5">
                    <span className="flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 text-[10px] font-mono font-bold">
                      {idx + 1}
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border truncate ${catStyle.badge}`}>
                      {sub.category || 'Process'}
                    </span>
                  </div>

                  {/* Phase Title */}
                  <h4 className="text-xs font-bold text-black dark:text-white truncate" title={sub.treatment_name || sub.name}>
                    {sub.treatment_name || sub.name || `Fasa #${idx + 1}`}
                  </h4>

                  {/* Summary Metric Chips */}
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-stroke/70 dark:border-strokedark/70 text-[10px] font-mono text-gray-500 dark:text-gray-400">
                    <span className="flex items-center gap-1 font-semibold text-primary dark:text-blue-400">
                      <Boxes className="h-3 w-3" />
                      {stepsCount} Langkah
                    </span>
                    {phaseTemp ? (
                      <span className="flex items-center gap-1 font-semibold text-rose-600 dark:text-rose-400">
                        <Flame className="h-3 w-3" />
                        {Math.round(phaseTemp)}°C
                      </span>
                    ) : null}
                    {phaseTime ? (
                      <span className="flex items-center gap-1 text-slate-600 dark:text-slate-300">
                        <Clock className="h-3 w-3 text-orange-500" />
                        {Math.round(phaseTime)}m
                      </span>
                    ) : null}
                  </div>

                  {/* Hover / Focus / Touch Quick Actions (Move, Duplicate, Delete) */}
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className={`absolute -top-2.5 right-2 flex items-center gap-1 bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg shadow-md px-1.5 py-0.5 z-10 transition-opacity ${
                      isSelected
                        ? 'opacity-100'
                        : 'opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100'
                    }`}
                  >
                    <button
                      type="button"
                      disabled={idx === 0}
                      onClick={() => onMoveSub && onMoveSub(idx, 'LEFT')}
                      aria-label="Geser Fasa ke Kiri"
                      className="p-1 text-gray-400 hover:text-black dark:hover:text-white disabled:opacity-30 transition"
                      title="Geser Fasa ke Kiri"
                    >
                      <ArrowLeft className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={idx === subPrograms.length - 1}
                      onClick={() => onMoveSub && onMoveSub(idx, 'RIGHT')}
                      aria-label="Geser Fasa ke Kanan"
                      className="p-1 text-gray-400 hover:text-black dark:hover:text-white disabled:opacity-30 transition"
                      title="Geser Fasa ke Kanan"
                    >
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDuplicateSub && onDuplicateSub(idx)}
                      aria-label="Duplikasi Seluruh Fasa Ini"
                      className="p-1 text-blue-500 hover:text-blue-700 transition"
                      title="Duplikasi Seluruh Fasa Ini"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteSub && onDeleteSub(idx)}
                      aria-label="Hapus Fasa Ini"
                      className="p-1 text-rose-500 hover:text-rose-700 transition"
                      title="Hapus Fasa Ini"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Pipeline Arrow Connector */}
                {idx < subPrograms.length - 1 && (
                  <div className="flex-shrink-0 text-gray-300 dark:text-gray-600 px-0.5">
                    <ChevronRight className="h-5 w-5" />
                  </div>
                )}
              </React.Fragment>
            );
          })
        )}
      </div>
    </div>
  );
}
