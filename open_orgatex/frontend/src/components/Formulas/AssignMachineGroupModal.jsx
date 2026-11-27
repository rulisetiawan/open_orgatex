import React, { useState, useEffect, useMemo } from 'react';
import { X, Send, CheckCircle2, Globe, Server, Layers, Search, Cpu } from 'lucide-react';
import api, { getApiErrorMessage } from '../../services/api';
import { useToast } from '../../context/ToastContext';

/**
 * Modal untuk mengirim (assign) 1 atau beberapa Formula (bulk) ke:
 * - Semua Grup & Mesin (Global)
 * - Per Grup Mesin (multi-select)
 * - Per Mesin Spesifik (multi-select dengan pencarian & pilih per grup)
 */
export default function AssignMachineGroupModal({
  isOpen,
  onClose,
  formulas = [], // array of formula objects (1 for single, >1 for bulk)
  machineGroups = [],
  onSaved,
}) {
  const { toast } = useToast();
  const isBulk = formulas.length > 1;
  const singleFormula = formulas.length === 1 ? formulas[0] : null;

  const [activeTab, setActiveTab] = useState('groups'); // 'groups' | 'machines'
  const [applyAll, setApplyAll] = useState(false);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [selectedMachines, setSelectedMachines] = useState([]);
  const [machineSearch, setMachineSearch] = useState('');
  const [bulkMode, setBulkMode] = useState('add'); // 'add' | 'replace'
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setMachineSearch('');
    if (singleFormula) {
      setApplyAll(Boolean(singleFormula.apply_all_groups));
      setSelectedGroups(Array.isArray(singleFormula.machine_groups) ? [...singleFormula.machine_groups] : []);
      setSelectedMachines(Array.isArray(singleFormula.machine_nos) ? [...singleFormula.machine_nos] : []);
      if (
        (!singleFormula.machine_groups || singleFormula.machine_groups.length === 0) &&
        singleFormula.machine_nos &&
        singleFormula.machine_nos.length > 0
      ) {
        setActiveTab('machines');
      } else {
        setActiveTab('groups');
      }
    } else {
      setApplyAll(false);
      setSelectedGroups([]);
      setSelectedMachines([]);
      setBulkMode('add');
      setActiveTab('groups');
    }
  }, [isOpen, singleFormula]);

  const allMachineNos = useMemo(() => {
    const list = [];
    machineGroups.forEach((g) => {
      (g.machines || []).forEach((m) => {
        if (m.machine_no && !list.includes(m.machine_no)) {
          list.push(m.machine_no);
        }
      });
    });
    return list;
  }, [machineGroups]);

  const filteredGroupsForMachines = useMemo(() => {
    const q = machineSearch.trim().toLowerCase();
    return machineGroups
      .map((g) => {
        const machs = (g.machines || []).filter((m) => {
          if (!q) return true;
          return (
            String(m.machine_no || '').toLowerCase().includes(q) ||
            String(m.display_name || '').toLowerCase().includes(q) ||
            String(g.group_name || '').toLowerCase().includes(q)
          );
        });
        return { ...g, machines: machs };
      })
      .filter((g) => g.machines.length > 0);
  }, [machineGroups, machineSearch]);

  if (!isOpen || formulas.length === 0) return null;

  const toggleGroup = (gName) => {
    setSelectedGroups((prev) =>
      prev.includes(gName) ? prev.filter((x) => x !== gName) : [...prev, gName]
    );
  };

  const toggleMachine = (mNo) => {
    setSelectedMachines((prev) =>
      prev.includes(mNo) ? prev.filter((x) => x !== mNo) : [...prev, mNo]
    );
  };

  const toggleAllMachinesInGroup = (grpMachines) => {
    const nos = (grpMachines || []).map((m) => m.machine_no);
    const allChecked = nos.length > 0 && nos.every((n) => selectedMachines.includes(n));
    if (allChecked) {
      setSelectedMachines((prev) => prev.filter((x) => !nos.includes(x)));
    } else {
      setSelectedMachines((prev) => Array.from(new Set([...prev, ...nos])));
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isBulk) {
        const res = await api.post('/formulas/bulk-assign-groups', {
          formula_ids: formulas.map((f) => f.id),
          machine_groups: applyAll ? [] : selectedGroups,
          machine_nos: applyAll ? [] : selectedMachines,
          apply_all_groups: applyAll,
          mode: bulkMode,
        });
        toast.success(res.data?.message || 'Formula berhasil dikirim ke grup / mesin.');
      } else {
        const res = await api.post(`/formulas/${singleFormula.id}/assign-groups`, {
          machine_groups: applyAll ? [] : selectedGroups,
          machine_nos: applyAll ? [] : selectedMachines,
          apply_all_groups: applyAll,
        });
        toast.success(res.data?.message || 'Target grup & mesin penerima berhasil diperbarui.');
      }
      onSaved?.();
      onClose();
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Gagal mengirim formula ke grup / mesin.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Kirim Formula ke Grup Mesin atau Per Mesin"
      onClick={onClose}
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-stroke dark:border-strokedark bg-gray-50/70 dark:bg-meta-4/30">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Send className="h-4.5 w-4.5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-black dark:text-white">
                {isBulk
                  ? `Kirim Massal (${formulas.length} Formula) ke Grup / Mesin`
                  : 'Kirim Formula ke Grup Mesin / Per Mesin'}
              </h3>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                {isBulk
                  ? 'Semua formula terpilih akan langsung tersedia di Program Studio untuk grup & mesin yang dicentang.'
                  : `${singleFormula.code} — ${singleFormula.name}`}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-black dark:hover:text-white hover:bg-gray-100 dark:hover:bg-meta-4"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Semua Grup Toggle */}
          <label
            className={`flex items-center justify-between p-3.5 rounded-lg border-2 cursor-pointer transition ${
              applyAll
                ? 'border-emerald-500 bg-emerald-50/60 dark:bg-emerald-950/30'
                : 'border-stroke dark:border-strokedark hover:border-primary/40'
            }`}
          >
            <div className="flex items-center gap-3">
              <Globe className={`h-5 w-5 ${applyAll ? 'text-emerald-600' : 'text-gray-400'}`} />
              <div>
                <div className="text-xs font-bold text-black dark:text-white">
                  Kirim ke Semua Grup & Mesin (Global)
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400">
                  Formula otomatis tersedia untuk seluruh mesin celup tanpa perlu pilih satu per satu.
                </div>
              </div>
            </div>
            <input
              type="checkbox"
              checked={applyAll}
              onChange={(e) => setApplyAll(e.target.checked)}
              className="h-4.5 w-4.5 accent-emerald-600 rounded"
            />
          </label>

          {isBulk && !applyAll && (
            <div className="flex flex-wrap items-center gap-3 p-2.5 rounded-lg bg-gray-50 dark:bg-meta-4/40 border border-stroke dark:border-strokedark text-xs">
              <span className="font-semibold text-gray-600 dark:text-gray-300">Mode Pengiriman Massal:</span>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="bulkMode"
                  checked={bulkMode === 'add'}
                  onChange={() => setBulkMode('add')}
                />
                <span>Tambahkan ke target yang sudah ada</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="bulkMode"
                  checked={bulkMode === 'replace'}
                  onChange={() => setBulkMode('replace')}
                />
                <span>Ganti seluruh target</span>
              </label>
            </div>
          )}

          {/* TAB SWITCHER: GRUP MESIN vs PER MESIN */}
          {!applyAll && (
            <>
              <div className="grid grid-cols-2 gap-1.5 p-1 rounded-lg bg-gray-100 dark:bg-meta-4/50 border border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setActiveTab('groups')}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md text-xs font-bold transition ${
                    activeTab === 'groups'
                      ? 'bg-white dark:bg-boxdark text-primary shadow-xs'
                      : 'text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
                >
                  <Layers className="h-3.5 w-3.5" />
                  <span>Per Grup Mesin ({selectedGroups.length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('machines')}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md text-xs font-bold transition ${
                    activeTab === 'machines'
                      ? 'bg-white dark:bg-boxdark text-cyan-700 dark:text-cyan-400 shadow-xs'
                      : 'text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
                >
                  <Cpu className="h-3.5 w-3.5" />
                  <span>Per Mesin Spesifik ({selectedMachines.length})</span>
                </button>
              </div>

              {/* TAB 1: GRUP MESIN */}
              {activeTab === 'groups' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Pilih Grup Mesin ({selectedGroups.length} dipilih)
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedGroups(machineGroups.map((g) => g.group_name))}
                        className="text-[11px] font-semibold text-primary hover:underline"
                      >
                        Pilih Semua
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedGroups([])}
                        className="text-[11px] font-semibold text-gray-400 hover:underline"
                      >
                        Kosongkan
                      </button>
                    </div>
                  </div>

                  {machineGroups.length === 0 ? (
                    <div className="p-4 text-center text-xs text-gray-400 border border-dashed rounded-lg">
                      Belum ada grup mesin ditemukan di database.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {machineGroups.map((grp) => {
                        const checked = selectedGroups.includes(grp.group_name);
                        const sampleMachines = (grp.machines || []).slice(0, 5).map((m) => m.machine_no).join(', ');
                        const moreCount = Math.max(0, (grp.machines || []).length - 5);
                        return (
                          <label
                            key={grp.group_name}
                            className={`flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer transition ${
                              checked
                                ? 'border-primary bg-primary/5 dark:bg-primary/15 shadow-xs'
                                : 'border-stroke dark:border-strokedark hover:border-gray-300 dark:hover:border-gray-600'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleGroup(grp.group_name)}
                              className="mt-0.5 h-4 w-4 accent-primary rounded"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-1">
                                <span className="text-xs font-bold text-black dark:text-white truncate">
                                  {grp.group_name}
                                </span>
                                <span className="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300">
                                  {grp.machine_count} mesin
                                </span>
                              </div>
                              {sampleMachines && (
                                <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                                  <Server className="inline h-2.5 w-2.5 mr-1 -mt-0.5" />
                                  {sampleMachines}
                                  {moreCount > 0 ? ` +${moreCount}` : ''}
                                </p>
                              )}
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: PER MESIN SPESIFIK */}
              {activeTab === 'machines' && (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="relative flex-1 min-w-[180px]">
                      <Search className="h-3.5 w-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={machineSearch}
                        onChange={(e) => setMachineSearch(e.target.value)}
                        placeholder="Cari kode mesin (mis. DA01, 1B, 12C)..."
                        className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-slate-900 text-black dark:text-white outline-none focus:border-primary"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedMachines([...allMachineNos])}
                        className="text-[11px] font-semibold text-cyan-700 dark:text-cyan-400 hover:underline"
                      >
                        Pilih Semua ({allMachineNos.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedMachines([])}
                        className="text-[11px] font-semibold text-gray-400 hover:underline"
                      >
                        Kosongkan
                      </button>
                    </div>
                  </div>

                  {filteredGroupsForMachines.length === 0 ? (
                    <div className="p-4 text-center text-xs text-gray-400 border border-dashed rounded-lg">
                      Tidak ada mesin yang cocok dengan pencarian.
                    </div>
                  ) : (
                    <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                      {filteredGroupsForMachines.map((grp) => {
                        const grpNos = grp.machines.map((m) => m.machine_no);
                        const allInGrp = grpNos.length > 0 && grpNos.every((n) => selectedMachines.includes(n));
                        return (
                          <div
                            key={grp.group_name}
                            className="p-3 rounded-lg border border-stroke dark:border-strokedark bg-gray-50/40 dark:bg-meta-4/20 space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-gray-700 dark:text-gray-200 flex items-center gap-1.5">
                                <Layers className="h-3 w-3 text-gray-400" />
                                {grp.group_name}
                              </span>
                              <button
                                type="button"
                                onClick={() => toggleAllMachinesInGroup(grp.machines)}
                                className="text-[10px] font-bold text-cyan-700 dark:text-cyan-400 hover:underline"
                              >
                                {allInGrp ? 'Batal Semua di Grup' : `Pilih Semua (${grp.machines.length})`}
                              </button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {grp.machines.map((m) => {
                                const active = selectedMachines.includes(m.machine_no);
                                return (
                                  <button
                                    key={m.machine_no}
                                    type="button"
                                    onClick={() => toggleMachine(m.machine_no)}
                                    title={m.display_name}
                                    className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-bold border transition ${
                                      active
                                        ? 'bg-cyan-600 text-white border-cyan-600 shadow-xs'
                                        : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-gray-300 border-stroke dark:border-gray-700 hover:border-cyan-500'
                                    }`}
                                  >
                                    {active ? '✓ ' : '+ '}
                                    {m.machine_no}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3.5 border-t border-stroke dark:border-strokedark bg-gray-50/70 dark:bg-meta-4/30">
          <div className="text-[11px] text-gray-600 dark:text-gray-300 flex items-center gap-1.5 font-semibold">
            <Layers className="h-3.5 w-3.5 text-primary" />
            <span>
              {applyAll
                ? 'Aktif di semua grup & mesin (Global)'
                : `${selectedGroups.length} grup mesin + ${selectedMachines.length} mesin spesifik`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-meta-4"
            >
              Batal
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSave}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 shadow-sm transition"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{saving ? 'Mengirim...' : 'Simpan & Kirim'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
