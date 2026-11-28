import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Calculator,
  Plus,
  Search,
  Send,
  Edit3,
  Trash2,
  Copy,
  RefreshCw,
  GitBranch,
  Table2,
  BookOpen,
  Sparkles,
  Globe,
  Layers,
  CheckSquare,
  Square,
  Sliders,
  Cpu,
} from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';
import { useToast } from '../context/ToastContext';
import FormulaEditorModal from '../components/Formulas/FormulaEditorModal';
import AssignMachineGroupModal from '../components/Formulas/AssignMachineGroupModal';
import { summarizeFormulaIndonesian } from '../utils/formulaEval';

const TYPE_BADGE = {
  MATH: { label: 'Matematika', icon: Calculator, cls: 'bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300' },
  IF_ELSE: { label: 'IF–ELSE', icon: GitBranch, cls: 'bg-purple-100 text-purple-800 dark:bg-purple-950/50 dark:text-purple-300' },
  RANGE_TABLE: { label: 'Tabel Rentang', icon: Table2, cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300' },
  LOOKUP_TABLE: { label: 'Tabel Pemetaan', icon: BookOpen, cls: 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300' },
};

export default function Formulas() {
  const { toast, confirm } = useToast();

  const [formulas, setFormulas] = useState([]);
  const [machineGroups, setMachineGroups] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterGroup, setFilterGroup] = useState('ALL');
  const [filterType, setFilterType] = useState('ALL');

  // Multi-select for bulk assign to Machine Groups
  const [selectedIds, setSelectedIds] = useState([]);

  // Modals
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorInitial, setEditorInitial] = useState(null);
  const [editorIsEdit, setEditorIsEdit] = useState(false);

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignTargets, setAssignTargets] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [fRes, gRes, tRes] = await Promise.all([
        api.get('/formulas/'),
        api.get('/formulas/machine-groups'),
        api.get('/formulas/templates'),
      ]);
      setFormulas(fRes.data?.formulas || []);
      setMachineGroups(gRes.data?.groups || []);
      setTemplates(tRes.data?.templates || []);
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Gagal memuat data formula.'));
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const filteredFormulas = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return formulas.filter((f) => {
      if (filterType !== 'ALL' && f.formula_type !== filterType) return false;
      if (filterGroup !== 'ALL') {
        if (!f.apply_all_groups && !(f.machine_groups || []).includes(filterGroup)) return false;
      }
      if (q) {
        const hay = `${f.code} ${f.name} ${f.description || ''} ${f.target_function_name || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [formulas, searchTerm, filterGroup, filterType]);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleCreateNew = () => {
    setEditorInitial(null);
    setEditorIsEdit(false);
    setEditorOpen(true);
  };

  const handleUseTemplate = (tmpl) => {
    setEditorInitial(tmpl);
    setEditorIsEdit(false);
    setShowTemplates(false);
    setEditorOpen(true);
  };

  const handleEdit = (f) => {
    setEditorInitial(f);
    setEditorIsEdit(true);
    setEditorOpen(true);
  };

  const handleDuplicate = (f) => {
    setEditorInitial({
      ...f,
      id: undefined,
      code: '',
      name: `${f.name} (Salinan)`,
    });
    setEditorIsEdit(false);
    setEditorOpen(true);
  };

  const handleDelete = async (f) => {
    const ok = await confirm(
      `Hapus formula "${f.name}" (${f.code})? Parameter step yang terhubung akan kembali ke nilai cadangan.`,
      { title: 'Hapus Formula', confirmText: 'Ya, Hapus', danger: true }
    );
    if (!ok) return;
    try {
      await api.delete(`/formulas/${f.id}`);
      toast.success(`Formula "${f.name}" dihapus.`);
      setSelectedIds((prev) => prev.filter((x) => x !== f.id));
      fetchAll();
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Gagal menghapus formula.'));
    }
  };

  const handleOpenAssignSingle = (f) => {
    setAssignTargets([f]);
    setAssignModalOpen(true);
  };

  const handleOpenAssignBulk = () => {
    const picked = formulas.filter((f) => selectedIds.includes(f.id));
    if (picked.length === 0) return;
    setAssignTargets(picked);
    setAssignModalOpen(true);
  };

  return (
    <div className="space-y-5">
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-black dark:text-white flex items-center gap-2">
            <Calculator className="h-6 w-6 text-primary" />
            Formula Global
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowTemplates((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded-lg border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700 transition"
          >
            <Sparkles className="h-4 w-4" />
            <span>Template Siap Pakai</span>
          </button>
          <button
            type="button"
            onClick={fetchAll}
            disabled={loading}
            className="p-2 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-gray-600 dark:text-gray-300 hover:text-primary transition"
            title="Muat ulang"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={handleCreateNew}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary/90 shadow-sm transition"
          >
            <Plus className="h-4 w-4" />
            <span>Buat Formula Baru</span>
          </button>
        </div>
      </div>

      {/* TEMPLATE GALLERY (Collapsible) */}
      {showTemplates && (
        <div className="p-4 rounded-xl border border-amber-300/70 dark:border-amber-700/60 bg-amber-50/50 dark:bg-amber-950/20 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-900 dark:text-amber-200 flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" />
              Template Formula
            </span>
            <button
              type="button"
              onClick={() => setShowTemplates(false)}
              className="text-xs text-amber-700 hover:underline"
            >
              Tutup
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.map((t) => {
              const tb = TYPE_BADGE[t.formula_type] || TYPE_BADGE.MATH;
              return (
                <div
                  key={t.code}
                  onClick={() => handleUseTemplate(t)}
                  className="p-3.5 rounded-lg bg-white dark:bg-boxdark border border-stroke dark:border-strokedark hover:border-primary cursor-pointer shadow-xs transition space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${tb.cls}`}>{tb.label}</span>
                    {t.output_mode === 'MULTI' && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
                        Multi-Param ({t.outputs?.length || 0})
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-bold text-black dark:text-white">{t.name}</div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2">{t.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* FILTER BAR & BULK ACTIONS */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3.5 rounded-xl bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
        <div className="flex flex-wrap items-center gap-2.5 flex-1">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Cari nama / kode formula..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-slate-900 text-black dark:text-white outline-none focus:border-primary"
            />
          </div>

          <select
            value={filterGroup}
            onChange={(e) => setFilterGroup(e.target.value)}
            className="text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-slate-900 px-3 py-1.5 text-black dark:text-white outline-none focus:border-primary"
          >
            <option value="ALL">Semua Grup Mesin ({machineGroups.length})</option>
            {machineGroups.map((g) => (
              <option key={g.group_name} value={g.group_name}>
                {g.group_id ? `${g.group_id} · ` : ''}{g.group_name} ({g.machine_count} mesin)
              </option>
            ))}
          </select>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-slate-900 px-3 py-1.5 text-black dark:text-white outline-none focus:border-primary"
          >
            <option value="ALL">Semua Jenis Formula</option>
            <option value="MATH">Rumus Matematika</option>
            <option value="IF_ELSE">Logika IF–ELSE</option>
            <option value="RANGE_TABLE">Tabel Rentang</option>
            <option value="LOOKUP_TABLE">Tabel Pemetaan</option>
          </select>

          {filteredFormulas.length > 0 && (
            <button
              type="button"
              onClick={() => {
                const allIds = filteredFormulas.map((f) => f.id);
                const allSelected = allIds.every((id) => selectedIds.includes(id));
                setSelectedIds(allSelected ? [] : allIds);
              }}
              className="px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/50 text-gray-700 dark:text-gray-200 hover:border-primary transition"
            >
              {filteredFormulas.every((f) => selectedIds.includes(f.id)) ? 'Batal Pilih Semua' : 'Pilih Semua'}
            </button>
          )}
        </div>

        {selectedIds.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-primary">{selectedIds.length} dipilih</span>
            <button
              type="button"
              onClick={handleOpenAssignBulk}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs transition"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Kirim Massal ke Grup / Mesin</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedIds([])}
              className="text-xs text-gray-400 hover:text-black dark:hover:text-white"
            >
              Batal
            </button>
          </div>
        )}
      </div>

      {/* FORMULA CARDS GRID */}
      {filteredFormulas.length === 0 ? (
        <div className="p-10 rounded-xl border border-dashed border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-center space-y-3">
          <Calculator className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto" />
          <div className="text-sm font-bold text-black dark:text-white">
            {formulas.length === 0 ? 'Belum Ada Formula Global' : 'Tidak ada formula yang cocok'}
          </div>
          <div className="flex items-center justify-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowTemplates(true)}
              className="px-3.5 py-2 text-xs font-bold rounded-lg border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100"
            >
              Lihat Template Siap Pakai
            </button>
            <button
              type="button"
              onClick={handleCreateNew}
              className="px-4 py-2 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary/90"
            >
              + Buat Formula Baru
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredFormulas.map((f) => {
            const tb = TYPE_BADGE[f.formula_type] || TYPE_BADGE.MATH;
            const TypeIcon = tb.icon;
            const isSelected = selectedIds.includes(f.id);
            return (
              <div
                key={f.id}
                className={`rounded-xl border bg-white dark:bg-boxdark p-4 flex flex-col justify-between gap-3 shadow-xs transition ${
                  isSelected
                    ? 'border-primary ring-2 ring-primary/20'
                    : 'border-stroke dark:border-strokedark hover:border-primary/40'
                }`}
              >
                <div className="space-y-2.5">
                  {/* Top row: checkbox + badges */}
                  <div className="flex items-start justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => toggleSelect(f.id)}
                      className="flex items-center gap-1.5 text-left group"
                    >
                      {isSelected ? (
                        <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                      ) : (
                        <Square className="h-4 w-4 text-gray-300 group-hover:text-primary shrink-0" />
                      )}
                      <span className="text-[11px] font-mono font-bold text-primary">{f.code}</span>
                    </button>
                    <div className="flex flex-wrap items-center gap-1 justify-end">
                      <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${tb.cls}`}>
                        <TypeIcon className="h-3 w-3" />
                        {tb.label}
                      </span>
                      {f.output_mode === 'MULTI' && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
                          <Sliders className="h-2.5 w-2.5" />
                          {f.outputs?.length || 0} Param
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Title & target */}
                  <div>
                    <h3 className="text-sm font-bold text-black dark:text-white leading-snug">{f.name}</h3>
                    {(() => {
                      const fnBadges = Array.isArray(f.outputs)
                        ? Array.from(
                            new Map(
                              f.outputs
                                .filter((o) => o?.target_function_id)
                                .map((o) => [String(o.target_function_id), `F${o.target_function_id}${o.target_function_name ? ` · ${o.target_function_name}` : ''}`])
                            ).values()
                          )
                        : [];
                      if (fnBadges.length > 1) {
                        return (
                          <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">
                            Target Campuran: {fnBadges.join(', ')}
                          </span>
                        );
                      }
                      if (f.target_function_id) {
                        return (
                          <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">
                            Target: F{f.target_function_id} · {f.target_function_name}
                          </span>
                        );
                      }
                      if (fnBadges.length === 1) {
                        return (
                          <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">
                            Target: {fnBadges[0]}
                          </span>
                        );
                      }
                      return null;
                    })()}
                    {f.description && (
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                        {f.description}
                      </p>
                    )}
                  </div>

                  {/* Rule Summary */}
                  <div className="p-2 rounded-lg bg-gray-50 dark:bg-meta-4/40 border border-stroke dark:border-strokedark text-[11px] font-mono text-gray-700 dark:text-gray-200 line-clamp-2">
                    {summarizeFormulaIndonesian(f)}
                  </div>

                  {/* Deployed Machine Groups & Specific Machines */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {f.apply_all_groups ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
                        <Globe className="h-3 w-3" /> Semua Grup & Mesin
                      </span>
                    ) : (
                      <>
                        {(f.machine_groups || []).map((gn) => (
                          <span
                            key={`grp-${gn}`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                          >
                            <Layers className="h-2.5 w-2.5" /> {gn}
                          </span>
                        ))}
                        {(f.machine_nos || []).slice(0, 6).map((mn) => (
                          <span
                            key={`mach-${mn}`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-cyan-100 text-cyan-800 dark:bg-cyan-950/50 dark:text-cyan-300"
                          >
                            <Cpu className="h-2.5 w-2.5" /> {mn}
                          </span>
                        ))}
                        {(f.machine_nos || []).length > 6 && (
                          <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-400">
                            +{f.machine_nos.length - 6} mesin
                          </span>
                        )}
                        {(f.machine_groups || []).length === 0 && (f.machine_nos || []).length === 0 && (
                          <span className="text-[10px] italic text-amber-600 dark:text-amber-400">
                            Belum dikirim ke grup / mesin
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="flex items-center justify-between pt-2.5 border-t border-stroke dark:border-strokedark">
                  <button
                    type="button"
                    onClick={() => handleOpenAssignSingle(f)}
                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 transition"
                  >
                    <Send className="h-3 w-3" />
                    <span>Kirim ke Grup / Mesin</span>
                  </button>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => handleEdit(f)}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-primary hover:bg-gray-100 dark:hover:bg-meta-4 transition"
                      title="Edit formula"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDuplicate(f)}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-primary hover:bg-gray-100 dark:hover:bg-meta-4 transition"
                      title="Duplikat formula"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(f)}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition"
                      title="Hapus formula"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODALS */}
      <FormulaEditorModal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        initialFormula={editorInitial}
        isEdit={editorIsEdit}
        machineGroups={machineGroups}
        onSaved={fetchAll}
      />

      <AssignMachineGroupModal
        isOpen={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        formulas={assignTargets}
        machineGroups={machineGroups}
        onSaved={() => {
          setSelectedIds([]);
          fetchAll();
        }}
      />
    </div>
  );
}
