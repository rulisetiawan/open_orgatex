import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import {
  X,
  Search,
  Plus,
  Flame,
  Clock,
  Droplet,
  Gauge,
  Boxes,
  CheckCircle2,
  BookOpen,
  Sparkles,
  Layers,
  ChevronRight
} from 'lucide-react';

const CATEGORIES = [
  { id: 'ALL', label: 'Semua Kategori' },
  { id: 'Pretreatment', label: 'Prapengolahan (S/B)' },
  { id: 'Dyeing', label: 'Pencelupan (Dyeing)' },
  { id: 'Washing', label: 'Pencucian Sabun' },
  { id: 'Rinse', label: 'Pembilasan' },
  { id: 'Finishing', label: 'Penyempurnaan' }
];

const CATEGORY_COLORS = {
  Pretreatment: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700',
  Dyeing: 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-700',
  Washing: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-700',
  Rinse: 'bg-cyan-100 text-cyan-800 border-cyan-300 dark:bg-cyan-950/40 dark:text-cyan-300 dark:border-cyan-700',
  Finishing: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700',
  General: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
};

export default function SubProgramDrawer({
  isOpen,
  onClose,
  onInsertSubProgram,
  subProgramsCount = 0
}) {
  const [treatments, setTreatments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [expandedTreatmentId, setExpandedTreatmentId] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchTreatments();
    }
  }, [isOpen]);

  const fetchTreatments = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/programs/treatments/');
      setTreatments(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil pustaka treatments:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredTreatments = useMemo(() => {
    return treatments.filter(t => {
      const matchCat = selectedCategory === 'ALL' || t.category === selectedCategory;
      const term = searchTerm.toLowerCase();
      const matchSearch =
        (t.name || '').toLowerCase().includes(term) ||
        (t.number || '').toLowerCase().includes(term) ||
        (t.comment || '').toLowerCase().includes(term);
      return matchCat && matchSearch;
    });
  }, [treatments, selectedCategory, searchTerm]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Katalog Sub-Program & Modul Fasa"
      onClick={onClose}
      className="fixed inset-0 z-[60] flex justify-end bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-white dark:bg-boxdark h-full shadow-2xl flex flex-col border-l border-stroke dark:border-strokedark animate-in slide-in-from-right duration-300"
      >
        
        {/* Drawer Header */}
        <div className="flex items-center justify-between p-5 border-b border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 text-primary rounded-xl">
              <BookOpen className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-black dark:text-white">
                  Katalog Sub-Program & Modul Fasa
                </h3>
                <span className="text-xs bg-primary/10 text-primary font-bold px-2 py-0.5 rounded-full font-mono">
                  {treatments.length} Modul Tersedia
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Pilih modul proses tekstil standar industri untuk langsung disisipkan ke resep celup.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-meta-4 rounded-lg transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="p-4 border-b border-stroke dark:border-strokedark space-y-3 bg-white dark:bg-boxdark">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Cari modul fasa (misal: Scouring, Disperse 130, Reaktif, Soaping, Bilas)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full text-xs pl-10 pr-4 py-2.5 rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/40 text-black dark:text-white outline-none focus:border-primary focus:bg-white dark:focus:bg-boxdark transition"
            />
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1">
            {CATEGORIES.map(cat => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`text-xs px-3 py-1.5 rounded-lg font-semibold flex-shrink-0 transition ${
                  selectedCategory === cat.id
                    ? 'bg-primary text-white shadow-xs'
                    : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-meta-4/80'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Treatment Cards List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="py-16 text-center text-gray-400 text-xs">
              Memuat katalog modul fasa...
            </div>
          ) : filteredTreatments.length === 0 ? (
            <div className="py-16 text-center text-gray-400 text-xs border-2 border-dashed border-stroke dark:border-strokedark rounded-xl">
              Tidak ada modul fasa yang cocok dengan pencarian <strong>"{searchTerm}"</strong>.
            </div>
          ) : (
            filteredTreatments.map((tr) => {
              const catClass = CATEGORY_COLORS[tr.category] || CATEGORY_COLORS.General;
              const p = tr.parameters || {};
              const isExpanded = expandedTreatmentId === tr.id;
              const stepsCount = tr.steps ? tr.steps.length : 0;

              return (
                <div
                  key={tr.id || tr.number}
                  className="rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-primary/50 transition-all p-4 space-y-3 shadow-xs"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-gray-500 bg-gray-100 dark:bg-meta-4 px-2 py-0.5 rounded">
                          {tr.number}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${catClass}`}>
                          {tr.category || 'Process'}
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-black dark:text-white">
                        {tr.name}
                      </h4>
                      <p className="text-xs text-gray-400">
                        {tr.comment || 'Modul proses tekstil standar OrgaTEX/SETEX'}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        onInsertSubProgram(tr);
                        onClose();
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-bold shadow-xs transition active:scale-95 flex-shrink-0"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>Sisipkan</span>
                    </button>
                  </div>

                  {/* Parameter Chips */}
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-stroke/60 dark:border-strokedark/60 text-xs font-mono">
                    <span className="flex items-center gap-1 px-2 py-1 rounded bg-gray-50 dark:bg-meta-4/30 border border-stroke dark:border-strokedark text-gray-700 dark:text-gray-300 font-semibold">
                      <Boxes className="h-3.5 w-3.5 text-primary" />
                      {stepsCount} Langkah Mikro
                    </span>

                    {p.temperature ? (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 text-rose-700 dark:text-rose-300 font-semibold">
                        <Flame className="h-3.5 w-3.5 text-rose-500" />
                        {p.temperature}°C
                      </span>
                    ) : null}

                    {p.hold_time ? (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-900/50 text-orange-700 dark:text-orange-300 font-semibold">
                        <Clock className="h-3.5 w-3.5 text-orange-500" />
                        {p.hold_time}m tahan
                      </span>
                    ) : null}

                    {p.water_level ? (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900/50 text-blue-700 dark:text-blue-300 font-semibold">
                        <Droplet className="h-3.5 w-3.5 text-blue-500" />
                        {p.water_level}L
                      </span>
                    ) : null}

                    {p.pump_speed ? (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 text-amber-700 dark:text-amber-300 font-semibold">
                        <Gauge className="h-3.5 w-3.5 text-amber-500" />
                        {p.pump_speed}% pompa
                      </span>
                    ) : null}
                  </div>

                  {/* Toggle Preview Steps Inside */}
                  <div>
                    <button
                      type="button"
                      onClick={() => setExpandedTreatmentId(isExpanded ? null : tr.id)}
                      className="text-[11px] font-semibold text-primary dark:text-blue-400 hover:underline flex items-center gap-1"
                    >
                      <span>{isExpanded ? 'Sembunyikan Langkah Mikro' : `Lihat ${stepsCount} Langkah di Dalamnya`}</span>
                      <ChevronRight className={`h-3.5 w-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                    </button>

                    {isExpanded && tr.steps && (
                      <div className="mt-2.5 space-y-1.5 pl-2 border-l-2 border-primary/30 max-h-48 overflow-y-auto">
                        {tr.steps.map((st, sIdx) => (
                          <div key={sIdx} className="text-[11px] flex items-center justify-between py-1 px-2 bg-gray-50 dark:bg-meta-4/30 rounded">
                            <span className="font-medium text-black dark:text-white">
                              {sIdx + 1}. {st.label || 'Langkah'}
                            </span>
                            <div className="flex items-center gap-1.5 text-gray-400 font-mono text-[10px]">
                              {(st.functions || []).map((f, fIdx) => (
                                <span key={fIdx} className="bg-white dark:bg-boxdark px-1.5 py-0.5 rounded border border-stroke dark:border-strokedark">
                                  F{f.function_id}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/20 flex items-center justify-between">
          <span className="text-xs text-gray-400">
            Resep aktif memiliki {subProgramsCount} fasa
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-gray-200 dark:bg-meta-4 text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-300 transition"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
