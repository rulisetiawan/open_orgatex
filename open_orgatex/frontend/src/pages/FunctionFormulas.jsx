import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Sliders,
  Search,
  Plus,
  Edit3,
  RefreshCw,
  Cpu,
  FileCog,
  Calculator,
  Layers,
  CheckCircle2,
  AlertCircle,
  Database,
} from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';
import { useToast } from '../context/ToastContext';
import typeconfData from '../data/typeconf_functions.json';
import FormulaEditorModal from '../components/Formulas/FormulaEditorModal';
import { summarizeFormulaIndonesian } from '../utils/formulaEval';

const ALL_TC_FUNCTIONS = typeconfData.functions || {};
const ALL_TC_PARAMETERS = typeconfData.parameters || {};

export default function FunctionFormulas() {
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState('mapping'); // 'mapping' | 'config'
  const [formulas, setFormulas] = useState([]);
  const [machineGroups, setMachineGroups] = useState([]);
  const [selectedMachine, setSelectedMachine] = useState('DA01');
  const [searchTerm, setSearchTerm] = useState('');
  const [onlyMapped, setOnlyMapped] = useState(false);
  const [loading, setLoading] = useState(false);

  // Machine HMI config inspection (TYPEFORM.CNF, MACHCONF.CNF, TYPECONF.CNF)
  const [machineConfig, setMachineConfig] = useState(null);
  const [configLoading, setConfigLoading] = useState(false);

  // Editor Modal
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorInitial, setEditorInitial] = useState(null);
  const [editorIsEdit, setEditorIsEdit] = useState(false);

  const allMachines = useMemo(() => {
    const list = [];
    const seen = new Set();
    for (const g of machineGroups) {
      for (const m of g.machines || []) {
        if (!seen.has(m.machine_no)) {
          seen.add(m.machine_no);
          list.push({ ...m, group_name: g.group_name });
        }
      }
    }
    return list.sort((a, b) => String(a.machine_no).localeCompare(String(b.machine_no)));
  }, [machineGroups]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [fRes, gRes] = await Promise.all([
        api.get('/formulas/'),
        api.get('/formulas/machine-groups'),
      ]);
      setFormulas(fRes.data?.formulas || []);
      const groups = gRes.data?.groups || [];
      setMachineGroups(groups);
      if (groups.length > 0) {
        const flat = groups.flatMap((g) => g.machines || []);
        if (flat.length > 0 && !flat.some((m) => m.machine_no === selectedMachine)) {
          setSelectedMachine(flat[0].machine_no);
        }
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Gagal memuat data Function Formula.'));
    } finally {
      setLoading(false);
    }
  }, [toast, selectedMachine]);

  const fetchMachineConfig = useCallback(async (machNo) => {
    if (!machNo) return;
    setConfigLoading(true);
    try {
      const res = await api.get(`/formulas/machine-config/${encodeURIComponent(machNo)}`);
      setMachineConfig(res.data || null);
    } catch (err) {
      setMachineConfig(null);
      toast.error(getApiErrorMessage(err, `Gagal membaca file config mesin ${machNo}.`));
    } finally {
      setConfigLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (selectedMachine) {
      fetchMachineConfig(selectedMachine);
    }
  }, [selectedMachine, fetchMachineConfig]);

  // Build map: functionId -> list of { formula, outputSpec } targeting that function
  const formulasByFunction = useMemo(() => {
    const map = {};
    const addEntry = (fnId, entry) => {
      const key = String(fnId);
      if (!map[key]) map[key] = [];
      map[key].push(entry);
    };

    for (const f of formulas) {
      if (f.output_mode === 'MULTI' && Array.isArray(f.outputs) && f.outputs.length > 0) {
        for (const o of f.outputs) {
          const fid = o.target_function_id || f.target_function_id;
          if (fid) {
            addEntry(fid, { formula: f, output: o });
          }
        }
      } else if (f.target_function_id) {
        addEntry(f.target_function_id, {
          formula: f,
          output: {
            key: 'value',
            label: f.name,
            unit: f.unit || '',
            default_param_slot: f.outputs?.[0]?.default_param_slot || 1,
          },
        });
      }
    }
    return map;
  }, [formulas]);

  const functionRows = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return Object.values(ALL_TC_FUNCTIONS)
      .filter((fn) => fn && fn.id && (fn.parameters?.length || 0) > 0)
      .map((fn) => {
        const mapped = formulasByFunction[String(fn.id)] || [];
        const params = (fn.parameters || []).slice(0, 6).map((pm, idx) => {
          const pd = ALL_TC_PARAMETERS[String(pm.definition_id)] || {};
          return {
            slot: idx + 1,
            name: pd.name || `Parameter ${idx + 1}`,
            unit: pd.unit || '',
            min: pm.minimum,
            max: pm.maximum,
            defaultVal: pm.default ?? 0,
          };
        });
        return { ...fn, params, mapped };
      })
      .filter((fn) => {
        if (onlyMapped && fn.mapped.length === 0) return false;
        if (q) {
          const hay = `f${fn.id} ${fn.name || ''} ${fn.params.map((p) => p.name).join(' ')} ${fn.mapped.map((m) => m.formula.name).join(' ')}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (b.mapped.length !== a.mapped.length) return b.mapped.length - a.mapped.length;
        return Number(a.id) - Number(b.id);
      });
  }, [formulasByFunction, searchTerm, onlyMapped]);

  const handleCreateForFunction = (fn) => {
    const autoOuts = fn.params.slice(0, Math.min(3, fn.params.length)).map((tp) => ({
      key: `p${tp.slot}`,
      label: tp.name,
      unit: tp.unit,
      decimal_places: 1,
      min_value: tp.min ?? null,
      max_value: tp.max !== undefined ? Math.round(tp.max) : null,
      default_fallback: tp.defaultVal ?? 0,
      default_param_slot: tp.slot,
      target_function_id: Number(fn.id),
      target_function_name: fn.name,
    }));
    setEditorInitial({
      name: `Formula F${fn.id} - ${fn.name}`,
      formula_type: 'IF_ELSE',
      output_mode: autoOuts.length > 1 ? 'MULTI' : 'SINGLE',
      target_function_id: Number(fn.id),
      target_function_name: fn.name,
      outputs: autoOuts,
      unit: autoOuts[0]?.unit || '',
      apply_all_groups: true,
    });
    setEditorIsEdit(false);
    setEditorOpen(true);
  };

  const handleEditFormula = (f) => {
    setEditorInitial(f);
    setEditorIsEdit(true);
    setEditorOpen(true);
  };

  return (
    <div className="space-y-5">
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-black dark:text-white flex items-center gap-2">
            <Sliders className="h-6 w-6 text-primary" />
            Function Formula
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg px-2.5 py-1.5">
            <Cpu className="h-4 w-4 text-primary" />
            <span className="text-[11px] font-bold text-gray-500">Mesin:</span>
            <select
              value={selectedMachine}
              onChange={(e) => setSelectedMachine(e.target.value)}
              className="text-xs font-mono font-bold bg-transparent text-black dark:text-white outline-none"
            >
              {allMachines.length === 0 && <option value="DA01">DA01</option>}
              {allMachines.map((m) => (
                <option key={m.machine_no} value={m.machine_no}>
                  {m.machine_no} · {m.group_id || m.group_name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => {
              fetchAll();
              fetchMachineConfig(selectedMachine);
            }}
            disabled={loading || configLoading}
            className="p-2 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-gray-600 dark:text-gray-300 hover:text-primary transition"
            title="Muat ulang"
          >
            <RefreshCw className={`h-4 w-4 ${loading || configLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* TABS */}
      <div className="flex flex-wrap items-center gap-2 border-b border-stroke dark:border-strokedark pb-2">
        <button
          type="button"
          onClick={() => setActiveTab('mapping')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold transition ${
            activeTab === 'mapping'
              ? 'bg-primary text-white shadow-xs'
              : 'bg-white dark:bg-boxdark text-gray-600 dark:text-gray-300 border border-stroke dark:border-strokedark hover:border-primary'
          }`}
        >
          <Layers className="h-4 w-4" />
          <span>Mapping Fungsi ({Object.keys(formulasByFunction).length})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('groups')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold transition ${
            activeTab === 'groups'
              ? 'bg-primary text-white shadow-xs'
              : 'bg-white dark:bg-boxdark text-gray-600 dark:text-gray-300 border border-stroke dark:border-strokedark hover:border-primary'
          }`}
        >
          <Cpu className="h-4 w-4" />
          <span>Grup ID Mesin ({machineGroups.length})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('config')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold transition ${
            activeTab === 'config'
              ? 'bg-primary text-white shadow-xs'
              : 'bg-white dark:bg-boxdark text-gray-600 dark:text-gray-300 border border-stroke dark:border-strokedark hover:border-primary'
          }`}
        >
          <FileCog className="h-4 w-4" />
          <span>Config Mesin ({selectedMachine})</span>
        </button>
      </div>

      {/* TAB 1: FUNCTION -> FORMULA MAPPING */}
      {activeTab === 'mapping' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Cari Fungsi Mesin (mis. F141, Temperature, Dosing, Fill Level)..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-stroke dark:border-gray-700 bg-transparent text-black dark:text-white outline-none focus:border-primary"
              />
            </div>
            <label className="flex items-center gap-1.5 text-xs font-bold text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyMapped}
                onChange={(e) => setOnlyMapped(e.target.checked)}
                className="accent-primary"
              />
              <span>Hanya yang sudah punya formula</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {functionRows.slice(0, 60).map((fn) => (
              <div
                key={fn.id}
                className={`rounded-xl border bg-white dark:bg-boxdark p-4 space-y-3 transition ${
                  fn.mapped.length > 0
                    ? 'border-indigo-300 dark:border-indigo-700/70'
                    : 'border-stroke dark:border-strokedark'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-black bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-200">
                      F{fn.id}
                    </span>
                    <h3 className="text-sm font-bold text-black dark:text-white">{fn.name}</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCreateForFunction(fn)}
                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold rounded-lg bg-primary text-white hover:bg-primary/90 shrink-0"
                  >
                    <Plus className="h-3.5 w-3.5" /> Buat Formula
                  </button>
                </div>

                {/* Parameters list */}
                <div className="flex flex-wrap gap-1.5">
                  {fn.params.map((p) => (
                    <span
                      key={p.slot}
                      className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-100 dark:bg-meta-4 text-gray-700 dark:text-gray-200"
                      title={`Min: ${p.min ?? '-'} | Maks: ${p.max ?? '-'} | Default: ${p.defaultVal ?? 0}`}
                    >
                      P{p.slot}: {p.name} {p.unit ? `(${p.unit})` : ''}
                    </span>
                  ))}
                </div>

                {/* Mapped formulas */}
                {fn.mapped.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-stroke dark:border-strokedark">
                    {fn.mapped.map((m, i) => (
                      <div
                        key={`${m.formula.id}-${m.output?.key || i}`}
                        className="flex items-center justify-between gap-2 p-2 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/25 border border-indigo-200/70 dark:border-indigo-800/50 text-xs"
                      >
                        <div className="min-w-0">
                          <div className="font-bold text-black dark:text-white truncate">
                            <span className="font-mono text-primary mr-1.5">{m.formula.code}</span>
                            {m.formula.name}
                          </div>
                          <div className="text-[10px] text-gray-500 truncate">
                            → P{m.output?.default_param_slot || 1}: {m.output?.label} · {summarizeFormulaIndonesian(m.formula)}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleEditFormula(m.formula)}
                          className="p-1.5 rounded text-indigo-600 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 shrink-0"
                          title="Edit Formula"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: MACHINE GROUP ID MAPPING */}
      {activeTab === 'groups' && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {machineGroups.map((grp) => (
              <div
                key={grp.group_name}
                className="rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark p-4 space-y-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="px-2 py-0.5 rounded font-mono text-[11px] font-black bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-200 shrink-0">
                      {grp.group_id || `GRP-${grp.group_no || '?'}`}
                    </span>
                    <h3 className="text-sm font-bold text-black dark:text-white truncate">{grp.group_name}</h3>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 text-[10px] font-bold">
                    <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-meta-4 text-gray-700 dark:text-gray-200">
                      {grp.machine_count} mesin
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300">
                      {grp.formula_count} fx
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {(grp.machines || []).map((m) => (
                    <button
                      key={m.machine_no}
                      type="button"
                      onClick={() => {
                        setSelectedMachine(m.machine_no);
                        setActiveTab('config');
                      }}
                      title={`${m.display_name || m.machine_no} · HMI: ${m.hmi_controller || m.controller_type || '-'} ${m.hmi_type ? `(${m.hmi_type})` : ''}`}
                      className={`px-2 py-1 rounded text-[11px] font-mono font-bold border transition flex items-center gap-1 ${
                        selectedMachine === m.machine_no
                          ? 'bg-primary text-white border-primary'
                          : 'bg-gray-50 dark:bg-slate-900 text-black dark:text-white border-stroke dark:border-gray-700 hover:border-primary'
                      }`}
                    >
                      <span>{m.machine_no}</span>
                      {m.hmi_controller && (
                        <span className={`text-[9px] font-sans px-1 rounded ${selectedMachine === m.machine_no ? 'bg-white/20 text-white' : 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'}`}>
                          {m.hmi_controller}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: MACHINE CONFIG INSPECTOR */}
      {activeTab === 'config' && (
        <div className="space-y-4">
          {configLoading ? (
            <div className="p-8 text-center text-xs text-gray-500">
              Membaca file konfigurasi HMI mesin {selectedMachine}...
            </div>
          ) : !machineConfig ? (
            <div className="p-6 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-xs text-gray-500">
              Tidak ada data config untuk mesin {selectedMachine}.
            </div>
          ) : (
            <>
              {/* File Availability Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  {
                    file: 'TYPEFORM.CNF',
                    desc: 'Global Formula & Function Formula HMI',
                    present: machineConfig.files?.['TYPEFORM.CNF'],
                    stat: `${machineConfig.typeform?.formulas?.length || 0} formula · ${machineConfig.typeform?.function_links_count || 0} link fungsi`,
                  },
                  {
                    file: 'MACHCONF.CNF',
                    desc: 'Konstanta mesin & kurva kalibrasi level/volume',
                    present: machineConfig.files?.['MACHCONF.CNF'],
                    stat: `${machineConfig.machconf?.constants?.length || 0} konstanta · ${machineConfig.machconf?.calibrations?.length || 0} kurva`,
                  },
                  {
                    file: 'TYPECONF.CNF',
                    desc: 'Definisi fungsi, parameter & controller params',
                    present: machineConfig.files?.['TYPECONF.CNF'],
                    stat: `${machineConfig.typeconf?.functions_count || 0} fungsi · ${machineConfig.typeconf?.controller_params_total || 0} ctrl param`,
                  },
                ].map((card) => (
                  <div
                    key={card.file}
                    className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-black text-black dark:text-white flex items-center gap-1.5">
                        <Database className="h-3.5 w-3.5 text-primary" />
                        {card.file}
                      </span>
                      {card.present ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                          <CheckCircle2 className="h-3 w-3" /> Tersedia
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300">
                          <AlertCircle className="h-3 w-3" /> Tidak ada
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500">{card.desc}</p>
                    <div className="text-[11px] font-mono font-bold text-indigo-600 dark:text-indigo-400">
                      {card.stat}
                    </div>
                  </div>
                ))}
              </div>

              {/* TYPEFORM.CNF Formulas */}
              <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-black uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
                    <Calculator className="h-4 w-4 text-primary" />
                    Daftar Formula di TYPEFORM.CNF ({machineConfig.typeform?.formulas?.length || 0})
                  </h3>
                  <span className="text-[11px] text-gray-500 font-mono">
                    {machineConfig.folder_name}/01_CONFIG_DARI_HMI/TYPEFORM.CNF
                  </span>
                </div>
                {machineConfig.typeform?.formulas?.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {machineConfig.typeform.formulas.map((tf) => (
                      <div
                        key={tf.id}
                        className="p-2.5 rounded-lg border border-stroke dark:border-strokedark bg-gray-50/70 dark:bg-meta-4/30 text-xs flex items-center gap-2"
                      >
                        <span className="px-1.5 py-0.5 rounded font-mono text-[10px] font-black bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 shrink-0">
                          #{tf.id}
                        </span>
                        <div className="min-w-0">
                          <div className="font-bold text-black dark:text-white truncate">{tf.name}</div>
                          {tf.name_local && tf.name_local !== tf.name && (
                            <div className="text-[10px] text-gray-500 truncate">{tf.name_local}</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 italic">
                    Mesin {selectedMachine} belum memiliki file TYPEFORM.CNF di folder HMI.
                  </p>
                )}
              </div>

              {/* MACHCONF.CNF Constants & Calibration Curves */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark space-y-2.5">
                  <h3 className="text-xs font-black uppercase tracking-wider text-black dark:text-white">
                    Konstanta & Batas Mesin — MACHCONF.CNF (cat=18)
                  </h3>
                  {machineConfig.machconf?.constants?.length > 0 ? (
                    <div className="space-y-1.5 max-h-64 overflow-y-auto">
                      {machineConfig.machconf.constants.map((c, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-2 text-xs p-2 rounded bg-gray-50 dark:bg-meta-4/30 border border-stroke/70 dark:border-strokedark"
                        >
                          <span className="font-mono font-bold text-gray-600 dark:text-gray-300">
                            Grp {c.group} · Idx {c.index}
                          </span>
                          <span className="font-mono text-[11px] text-black dark:text-white truncate">
                            {c.values.join(', ')}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500 italic">Tidak ada data konstanta MACHCONF.CNF.</p>
                  )}
                </div>

                <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark space-y-2.5">
                  <h3 className="text-xs font-black uppercase tracking-wider text-black dark:text-white">
                    Tabel Kalibrasi (Level % → Liter) — MACHCONF.CNF (cat=75)
                  </h3>
                  {machineConfig.machconf?.calibrations?.length > 0 ? (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {machineConfig.machconf.calibrations.map((cal, idx) => (
                        <div
                          key={idx}
                          className="p-2 rounded bg-gray-50 dark:bg-meta-4/30 border border-stroke/70 dark:border-strokedark space-y-1"
                        >
                          <div className="text-[11px] font-mono font-bold text-indigo-700 dark:text-indigo-300">
                            Kurva Grp {cal.group} · Idx {cal.index}
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {cal.points.map((pt, pIdx) => (
                              <span
                                key={pIdx}
                                className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white"
                              >
                                {pt.x} → <strong>{pt.y}</strong>
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500 italic">Tidak ada data kurva kalibrasi MACHCONF.CNF.</p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* FORMULA EDITOR MODAL */}
      <FormulaEditorModal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        initialFormula={editorInitial}
        isEdit={editorIsEdit}
        isTemplateSeed={!editorIsEdit && Boolean(editorInitial)}
        machineGroups={machineGroups}
        onSaved={fetchAll}
      />
    </div>
  );
}
