import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  Save,
  Calculator,
  GitBranch,
  Table2,
  ListChecks,
  Plus,
  Trash2,
  Play,
  CheckCircle2,
  AlertTriangle,
  Sliders,
  Globe,
  Sparkles,
} from 'lucide-react';
import api, { getApiErrorMessage } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import typeconfData from '../../data/typeconf_functions.json';
import {
  DEFAULT_BATCH_VARIABLES,
  NUMERIC_VAR_KEYS,
  NUMERIC_OPERATORS,
  TEXT_OPERATORS,
  FABRIC_TYPE_OPTIONS,
  COLOR_SHADE_OPTIONS,
  DYE_TYPE_OPTIONS,
  evaluateFormulaClient,
  summarizeFormulaIndonesian,
} from '../../utils/formulaEval';

const ALL_TC_FUNCTIONS = typeconfData.functions || {};
const ALL_TC_PARAMETERS = typeconfData.parameters || {};
const ALL_TC_CHOICES = typeconfData.text_choices || {};

const FORMULA_TYPE_TABS = [
  { id: 'MATH', label: 'Rumus Matematika', desc: 'Hitung langsung (+ − × ÷)', icon: Calculator },
  { id: 'IF_ELSE', label: 'Logika IF–ELSE', desc: 'Aturan JIKA / MAKA fleksibel', icon: GitBranch },
  { id: 'RANGE_TABLE', label: 'Tabel Rentang', desc: 'Kelas angka (seperti Excel)', icon: Table2 },
  { id: 'LOOKUP_TABLE', label: 'Tabel Pemetaan', desc: 'Mapping Jenis Kain / Warna', icon: ListChecks },
];

const QUICK_MATH_TOKENS = [
  { label: '+', insert: ' + ' },
  { label: '−', insert: ' - ' },
  { label: '×', insert: ' * ' },
  { label: '÷', insert: ' / ' },
  { label: '(', insert: '(' },
  { label: ')', insert: ')' },
  { label: 'round()', insert: 'round(, 0)' },
  { label: 'min()', insert: 'min(, )' },
  { label: 'max()', insert: 'max(, )' },
];

function getDefaultDefinition(type, outputMode, outputs) {
  const outKeys = (outputs || []).map((o) => o.key);
  const emptyMulti = (val = '0') => Object.fromEntries(outKeys.map((k) => [k, val]));

  if (type === 'MATH') {
    return outputMode === 'MULTI'
      ? { expressions: emptyMulti('0') }
      : { expression: 'fabric_weight_kg * liquor_ratio' };
  }
  if (type === 'IF_ELSE') {
    return {
      rules: [
        {
          label: 'Kondisi 1',
          logic: 'AND',
          conditions: [{ var: 'fabric_type', op: 'equals', value: 'POLYESTER' }],
          result_expr: '130',
          outputs: emptyMulti('130'),
        },
      ],
      else_expr: '60',
      else_outputs: emptyMulti('60'),
    };
  }
  if (type === 'RANGE_TABLE') {
    return {
      input_var: 'fabric_weight_kg',
      rows: [
        { min: 0, max: 150, result_expr: '30', outputs: emptyMulti('30'), label: 'Lot Kecil' },
        { min: 150.01, max: 350, result_expr: '45', outputs: emptyMulti('45'), label: 'Lot Sedang' },
        { min: 350.01, max: null, result_expr: '60', outputs: emptyMulti('60'), label: 'Lot Besar' },
      ],
      default_expr: '35',
      default_outputs: emptyMulti('35'),
    };
  }
  // LOOKUP_TABLE
  return {
    input_var: 'fabric_type',
    match_mode: 'contains',
    rows: [
      { match_values: 'POLYESTER, PES', match_mode: 'contains', result_expr: '130', outputs: emptyMulti('130'), label: 'Polyester' },
      { match_values: 'COTTON, CM', match_mode: 'contains', result_expr: '60', outputs: emptyMulti('60'), label: 'Cotton' },
      { match_values: 'RAYON', match_mode: 'contains', result_expr: '50', outputs: emptyMulti('50'), label: 'Rayon' },
    ],
    default_expr: '60',
    default_outputs: emptyMulti('60'),
  };
}

function getParamChoices(paramDef) {
  if (!paramDef || !paramDef.scale || paramDef.scale.mode !== 16) return [];
  const grp = paramDef.scale2?.text_group ?? paramDef.scale?.text_table_id;
  return ALL_TC_CHOICES[String(grp)] || [];
}

/**
 * Editor Visual 2-Kolom untuk membuat/mengedit Formula Parameter:
 * - Kiri: Visual Builder No-Code (4 tipe + Single/Multi-Parameter + Dropdown TYPECONF & Variabel Batch)
 * - Kanan: Simulator Uji Coba Instan (Real-Time 0ms)
 */
export default function FormulaEditorModal({
  isOpen,
  onClose,
  initialFormula = null,
  isEdit = false,
  isTemplateSeed = false,
  machineGroups = [],
  onSaved,
}) {
  const { toast } = useToast();
  const isEditing = Boolean((isEdit || !isTemplateSeed) && initialFormula && initialFormula.id);

  // Basic metadata
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [formulaType, setFormulaType] = useState('MATH');
  const [outputMode, setOutputMode] = useState('SINGLE');
  const [targetFunctionId, setTargetFunctionId] = useState('');
  const [unit, setUnit] = useState('');
  const [decimalPlaces, setDecimalPlaces] = useState(1);
  const [minValue, setMinValue] = useState('');
  const [maxValue, setMaxValue] = useState('');
  const [defaultFallback, setDefaultFallback] = useState(0);

  // Outputs definition (for MULTI mode, or synced 1 item for SINGLE)
  const [outputs, setOutputs] = useState([
    { key: 'p1', label: 'Parameter 1', unit: '', decimal_places: 1, min_value: null, max_value: null, default_fallback: 0, default_param_slot: 1 },
    { key: 'p2', label: 'Parameter 2', unit: '', decimal_places: 1, min_value: null, max_value: null, default_fallback: 0, default_param_slot: 2 },
  ]);

  // Formula definition object
  const [definition, setDefinition] = useState(() => getDefaultDefinition('MATH', 'SINGLE', []));

  // Quick machine group & per-machine assignment
  const [applyAllGroups, setApplyAllGroups] = useState(true);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [selectedMachines, setSelectedMachines] = useState([]);
  const [machineFilter, setMachineFilter] = useState('');

  // Active math input target for chip insertion
  const [activeMathTarget, setActiveMathTarget] = useState(null); // e.g. { kind: 'math', key: 'expression' }

  // Live simulator context
  const [simCtx, setSimCtx] = useState({
    fabric_weight_kg: 350,
    liquor_ratio: 8,
    fabric_length: 200,
    fabric_gsm: 180,
    chamber_count: 2,
    machine_capacity_kg: 350,
    fabric_type: 'COTTON',
    color_shade: 'TUA',
    dye_type: 'REACTIVE',
    redye: '0',
    article: 'CM 30S RIB 100% Cotton',
    color_name: 'UNGU TUA',
    color_code: '1650159',
    customer: 'PT. SMM JETFLOW',
  });

  const [saving, setSaving] = useState(false);

  // Sorted list of TYPECONF functions for target dropdown
  const tcFunctionOptions = useMemo(() => {
    return Object.values(ALL_TC_FUNCTIONS)
      .filter((f) => f && f.id && (f.parameters?.length || 0) > 0)
      .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  }, []);

  const selectedTcFunction = targetFunctionId ? ALL_TC_FUNCTIONS[String(targetFunctionId)] : null;

  const tcFunctionParams = useMemo(() => {
    if (!selectedTcFunction?.parameters) return [];
    return selectedTcFunction.parameters.slice(0, 6).map((pMeta, idx) => {
      const pDef = ALL_TC_PARAMETERS[String(pMeta.definition_id)] || {};
      return {
        slot: idx + 1,
        name: pDef.name || `Parameter ${idx + 1}`,
        unit: pDef.unit || '',
        min: pMeta.minimum,
        max: pMeta.maximum,
        defaultVal: pMeta.default ?? 0,
        choices: getParamChoices(pDef),
      };
    });
  }, [selectedTcFunction]);

  // Initialize state when modal opens
  useEffect(() => {
    if (!isOpen) return;
    if (initialFormula) {
      const fType = initialFormula.formula_type || 'MATH';
      const oMode = initialFormula.output_mode || 'SINGLE';
      const initOuts =
        Array.isArray(initialFormula.outputs) && initialFormula.outputs.length > 0
          ? initialFormula.outputs.map((o) => ({ ...o }))
          : [
              { key: 'p1', label: 'Parameter 1', unit: '', decimal_places: 1, min_value: null, max_value: null, default_fallback: 0, default_param_slot: 1 },
              { key: 'p2', label: 'Parameter 2', unit: '', decimal_places: 1, min_value: null, max_value: null, default_fallback: 0, default_param_slot: 2 },
            ];
      setName(initialFormula.name || '');
      setCode(isTemplateSeed ? '' : initialFormula.code || '');
      setDescription(initialFormula.description || '');
      setFormulaType(fType);
      setOutputMode(oMode);
      setTargetFunctionId(initialFormula.target_function_id ? String(initialFormula.target_function_id) : '');
      setUnit(initialFormula.unit || '');
      setDecimalPlaces(initialFormula.decimal_places ?? 1);
      setMinValue(initialFormula.min_value ?? '');
      setMaxValue(initialFormula.max_value ?? '');
      setDefaultFallback(initialFormula.default_fallback ?? 0);
      setOutputs(initOuts);
      setDefinition(initialFormula.definition ? JSON.parse(JSON.stringify(initialFormula.definition)) : getDefaultDefinition(fType, oMode, initOuts));
      setApplyAllGroups(isTemplateSeed ? true : Boolean(initialFormula.apply_all_groups));
      setSelectedGroups(Array.isArray(initialFormula.machine_groups) ? [...initialFormula.machine_groups] : []);
      setSelectedMachines(Array.isArray(initialFormula.machine_nos) ? [...initialFormula.machine_nos] : []);
    } else {
      const defOuts = [
        { key: 'p1', label: 'Target Suhu', unit: '°C', decimal_places: 1, min_value: 20, max_value: 140, default_fallback: 60, default_param_slot: 1 },
        { key: 'p2', label: 'Hold Time', unit: 'min', decimal_places: 0, min_value: 1, max_value: 180, default_fallback: 45, default_param_slot: 3 },
      ];
      setName('');
      setCode('');
      setDescription('');
      setFormulaType('MATH');
      setOutputMode('SINGLE');
      setTargetFunctionId('');
      setUnit('L');
      setDecimalPlaces(1);
      setMinValue('');
      setMaxValue('');
      setDefaultFallback(0);
      setOutputs(defOuts);
      setDefinition(getDefaultDefinition('MATH', 'SINGLE', defOuts));
      setApplyAllGroups(true);
      setSelectedGroups([]);
      setSelectedMachines([]);
    }
  }, [isOpen, initialFormula, isTemplateSeed]);

  // Switch formula type cleanly
  const handleSwitchType = (newType) => {
    if (newType === formulaType) return;
    setFormulaType(newType);
    setDefinition(getDefaultDefinition(newType, outputMode, outputs));
  };

  // Switch output mode cleanly
  const handleSwitchOutputMode = (newMode) => {
    if (newMode === outputMode) return;
    setOutputMode(newMode);
    if (newMode === 'MULTI' && tcFunctionParams.length > 0) {
      const autoOuts = tcFunctionParams.slice(0, 3).map((tp) => ({
        key: `p${tp.slot}`,
        label: tp.name,
        unit: tp.unit,
        decimal_places: 1,
        min_value: tp.min,
        max_value: tp.max,
        default_fallback: tp.defaultVal,
        default_param_slot: tp.slot,
      }));
      setOutputs(autoOuts);
      setDefinition(getDefaultDefinition(formulaType, 'MULTI', autoOuts));
    } else {
      setDefinition(getDefaultDefinition(formulaType, newMode, outputs));
    }
  };

  // When user picks a target TYPECONF function from dropdown
  const handleSelectTargetFunction = (fnIdStr) => {
    setTargetFunctionId(fnIdStr);
    const fnObj = fnIdStr ? ALL_TC_FUNCTIONS[String(fnIdStr)] : null;
    if (!fnObj?.parameters?.length) return;
    const p0Meta = fnObj.parameters[0];
    const p0Def = ALL_TC_PARAMETERS[String(p0Meta.definition_id)] || {};
    if (outputMode === 'SINGLE') {
      if (p0Def.unit) setUnit(p0Def.unit);
      if (p0Meta.minimum !== undefined) setMinValue(p0Meta.minimum);
      if (p0Meta.maximum !== undefined) setMaxValue(Math.round(p0Meta.maximum));
    } else {
      const autoOuts = fnObj.parameters.slice(0, 3).map((pm, idx) => {
        const pd = ALL_TC_PARAMETERS[String(pm.definition_id)] || {};
        return {
          key: `p${idx + 1}`,
          label: pd.name || `Parameter ${idx + 1}`,
          unit: pd.unit || '',
          decimal_places: 1,
          min_value: pm.minimum ?? null,
          max_value: pm.maximum !== undefined ? Math.round(pm.maximum) : null,
          default_fallback: pm.default ?? 0,
          default_param_slot: idx + 1,
        };
      });
      setOutputs(autoOuts);
      setDefinition(getDefaultDefinition(formulaType, 'MULTI', autoOuts));
    }
  };

  // Live preview object & evaluation
  const previewFormulaObj = useMemo(
    () => ({
      name: name || 'Formula Baru',
      formula_type: formulaType,
      output_mode: outputMode,
      outputs: outputMode === 'MULTI' ? outputs : null,
      definition,
      unit,
      decimal_places: Number(decimalPlaces) || 0,
      min_value: minValue === '' ? null : Number(minValue),
      max_value: maxValue === '' ? null : Number(maxValue),
      default_fallback: Number(defaultFallback) || 0,
    }),
    [name, formulaType, outputMode, outputs, definition, unit, decimalPlaces, minValue, maxValue, defaultFallback]
  );

  const simResult = useMemo(() => evaluateFormulaClient(previewFormulaObj, simCtx), [previewFormulaObj, simCtx]);
  const humanSummary = useMemo(() => summarizeFormulaIndonesian(previewFormulaObj), [previewFormulaObj]);

  if (!isOpen) return null;

  // Insert variable/operator token into currently active math input
  const insertToken = (tokenStr) => {
    if (formulaType === 'MATH' && outputMode === 'SINGLE') {
      setDefinition((d) => ({ ...d, expression: `${d.expression || ''}${tokenStr}` }));
      return;
    }
    if (activeMathTarget) {
      activeMathTarget(tokenStr);
    } else if (formulaType === 'MATH' && outputMode === 'MULTI' && outputs.length > 0) {
      const k = outputs[0].key;
      setDefinition((d) => ({
        ...d,
        expressions: { ...(d.expressions || {}), [k]: `${d.expressions?.[k] || ''}${tokenStr}` },
      }));
    }
  };

  // Helper: render value input for condition (dropdown if variable has options!)
  const renderConditionValueInput = (cond, onChange) => {
    const varMeta = DEFAULT_BATCH_VARIABLES.find((v) => v.key === cond.var);
    if (varMeta?.type === 'select' && Array.isArray(varMeta.options)) {
      return (
        <select
          value={cond.value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 min-w-[110px] text-xs font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
        >
          <option value="">-- Pilih --</option>
          {varMeta.options.map((opt) => (
            <option key={opt} value={opt}>
              {varMeta.option_labels?.[opt] || opt}
            </option>
          ))}
        </select>
      );
    }
    return (
      <input
        type={varMeta?.type === 'number' ? 'number' : 'text'}
        step="any"
        value={cond.value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={varMeta?.type === 'number' ? 'Angka' : 'Teks / kata kunci'}
        className="flex-1 min-w-[90px] text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
      />
    );
  };

  // Helper: render result expression input(s) for SINGLE or MULTI output
  const renderResultInputs = (singleVal, onSingleChange, multiObj, onMultiChange, compact = false) => {
    if (outputMode === 'SINGLE') {
      // If target function's P1 has discrete choices, offer a quick dropdown too
      const singleChoices = tcFunctionParams[0]?.choices || [];
      return (
        <div className="flex items-center gap-1.5 flex-1">
          {singleChoices.length > 0 && (
            <select
              value={singleVal ?? ''}
              onChange={(e) => onSingleChange(e.target.value)}
              className="text-xs font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
            >
              <option value="">Pilihan Mesin...</option>
              {singleChoices.map((c) => (
                <option key={c.value} value={String(c.value)}>
                  {c.text} ({c.value})
                </option>
              ))}
            </select>
          )}
          <input
            type="text"
            value={singleVal ?? ''}
            onFocus={() => setActiveMathTarget(() => (tok) => onSingleChange(`${singleVal ?? ''}${tok}`))}
            onChange={(e) => onSingleChange(e.target.value)}
            placeholder="Angka atau rumus (mis. fabric_weight_kg * 8)"
            className="w-full text-xs font-mono font-bold rounded border border-indigo-300 dark:border-indigo-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-black dark:text-white outline-none focus:border-primary"
          />
          {unit && !compact && (
            <span className="shrink-0 text-[11px] font-mono font-bold text-gray-500 bg-gray-100 dark:bg-meta-4 px-2 py-1 rounded">
              {unit}
            </span>
          )}
        </div>
      );
    }

    // MULTI output inputs
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 flex-1">
        {outputs.map((o) => {
          const val = multiObj?.[o.key] ?? '';
          return (
            <div key={o.key} className="space-y-0.5">
              <label className="block text-[10px] font-bold text-indigo-700 dark:text-indigo-300 truncate">
                P{o.default_param_slot || '?'}: {o.label} {o.unit ? `(${o.unit})` : ''}
              </label>
              <input
                type="text"
                value={val}
                onFocus={() =>
                  setActiveMathTarget(() => (tok) => onMultiChange(o.key, `${val}${tok}`))
                }
                onChange={(e) => onMultiChange(o.key, e.target.value)}
                placeholder="Angka / rumus"
                className="w-full text-xs font-mono font-bold rounded border border-indigo-300 dark:border-indigo-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white outline-none focus:border-primary"
              />
            </div>
          );
        })}
      </div>
    );
  };

  const handleSave = async () => {
    if (!name.trim()) {
      toast.warning('Nama formula wajib diisi.');
      return;
    }
    if (!simResult.ok) {
      toast.error(`Perbaiki error rumus terlebih dahulu: ${simResult.error}`);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        code: code.trim() || null,
        name: name.trim(),
        description: description.trim(),
        formula_type: formulaType,
        output_mode: outputMode,
        target_function_id: targetFunctionId ? Number(targetFunctionId) : null,
        target_function_name: selectedTcFunction?.name || null,
        outputs: outputMode === 'MULTI' ? outputs : null,
        definition,
        unit: unit.trim(),
        decimal_places: Number(decimalPlaces) || 0,
        min_value: minValue === '' ? null : Number(minValue),
        max_value: maxValue === '' ? null : Number(maxValue),
        default_fallback: Number(defaultFallback) || 0,
        apply_all_groups: applyAllGroups,
        machine_groups: applyAllGroups ? [] : selectedGroups,
        machine_nos: applyAllGroups ? [] : selectedMachines,
      };
      if (isEditing) {
        await api.put(`/formulas/${initialFormula.id}`, payload);
        toast.success(`Formula "${payload.name}" berhasil diperbarui.`);
      } else {
        await api.post('/formulas/', payload);
        toast.success(`Formula "${payload.name}" berhasil dibuat & siap dipakai!`);
      }
      onSaved?.();
      onClose();
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Gagal menyimpan formula.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Editor Formula Parameter"
      onClick={onClose}
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/65 backdrop-blur-sm p-3 sm:p-4 animate-in fade-in"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-6xl h-[92vh] rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark shadow-2xl flex flex-col overflow-hidden"
      >
        {/* TOP HEADER */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-stroke dark:border-strokedark bg-gray-50/80 dark:bg-meta-4/30">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-lg bg-primary text-white flex items-center justify-center shadow-xs">
              <Calculator className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-black dark:text-white">
                {isEditing ? `Edit Formula: ${initialFormula.code}` : 'Buat Formula Parameter Baru'}
              </h2>
              <p className="text-[11px] text-gray-500">
                Susun rumus secara visual dengan dropdown & uji langsung hasilnya di Simulator sebelah kanan.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-black dark:hover:text-white hover:bg-gray-100 dark:hover:bg-meta-4"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* MAIN 2-COLUMN BODY */}
        <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12">
          {/* LEFT: VISUAL BUILDER (8 cols) */}
          <div className="lg:col-span-8 overflow-y-auto p-5 space-y-5 border-r border-stroke dark:border-strokedark">
            {/* 1. IDENTITAS & TARGET FUNGSI */}
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
              <div className="sm:col-span-6">
                <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 mb-1">
                  Nama Formula *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Contoh: Volume Air Otomatis / Suhu Jenis Kain"
                  className="w-full text-xs font-bold rounded-lg border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-3 py-2 text-black dark:text-white outline-none focus:border-primary"
                />
              </div>
              <div className="sm:col-span-3">
                <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 mb-1">
                  Kode (Opsional)
                </label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="Auto (FX-...)"
                  className="w-full text-xs font-mono font-bold rounded-lg border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-3 py-2 text-black dark:text-white outline-none focus:border-primary"
                />
              </div>
              <div className="sm:col-span-3">
                <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 mb-1">
                  Target Fungsi Mesin
                </label>
                <select
                  value={targetFunctionId}
                  onChange={(e) => handleSelectTargetFunction(e.target.value)}
                  className="w-full text-xs font-semibold rounded-lg border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2.5 py-2 text-black dark:text-white outline-none focus:border-primary"
                >
                  <option value="">Umum / Semua Fungsi</option>
                  {tcFunctionOptions.map((fn) => (
                    <option key={fn.id} value={fn.id}>
                      F{fn.id} · {fn.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* 2. MODE OUTPUT (SINGLE vs MULTI-PARAMETER) */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-800/60">
              <div className="flex items-center gap-2">
                <Sliders className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <span className="text-xs font-bold text-black dark:text-white">Jumlah Parameter yang Diisi:</span>
              </div>
              <div className="flex rounded-lg overflow-hidden border border-indigo-300 dark:border-indigo-700 text-xs font-bold">
                <button
                  type="button"
                  onClick={() => handleSwitchOutputMode('SINGLE')}
                  className={`px-3 py-1.5 transition ${
                    outputMode === 'SINGLE'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-gray-300'
                  }`}
                >
                  1 Parameter (Tunggal)
                </button>
                <button
                  type="button"
                  onClick={() => handleSwitchOutputMode('MULTI')}
                  className={`px-3 py-1.5 transition ${
                    outputMode === 'MULTI'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-gray-300'
                  }`}
                >
                  Banyak Parameter (Paket Step)
                </button>
              </div>
            </div>

            {/* KONFIGURASI OUTPUT MULTI-PARAMETER */}
            {outputMode === 'MULTI' ? (
              <div className="p-3 rounded-lg border border-stroke dark:border-strokedark bg-gray-50/60 dark:bg-meta-4/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300">
                    Daftar Parameter Output ({outputs.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      const nextIdx = outputs.length + 1;
                      const nextKey = `p${nextIdx}`;
                      setOutputs((prev) => [
                        ...prev,
                        { key: nextKey, label: `Parameter ${nextIdx}`, unit: '', decimal_places: 1, min_value: null, max_value: null, default_fallback: 0, default_param_slot: Math.min(6, nextIdx) },
                      ]);
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-[11px] font-bold rounded bg-indigo-600 text-white hover:bg-indigo-700"
                  >
                    <Plus className="h-3 w-3" /> Tambah Output
                  </button>
                </div>
                <div className="space-y-1.5">
                  {outputs.map((o, idx) => (
                    <div key={o.key} className="grid grid-cols-12 gap-1.5 items-center">
                      <select
                        value={o.default_param_slot || 1}
                        onChange={(e) => {
                          const slot = Number(e.target.value);
                          const tcP = tcFunctionParams.find((tp) => tp.slot === slot);
                          setOutputs((prev) =>
                            prev.map((item, i) =>
                              i === idx
                                ? {
                                    ...item,
                                    default_param_slot: slot,
                                    ...(tcP ? { label: tcP.name, unit: tcP.unit, min_value: tcP.min, max_value: Math.round(tcP.max) } : {}),
                                  }
                                : item
                            )
                          );
                        }}
                        className="col-span-3 text-[11px] font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-1.5 py-1 text-black dark:text-white"
                      >
                        {tcFunctionParams.length > 0
                          ? tcFunctionParams.map((tp) => (
                              <option key={tp.slot} value={tp.slot}>
                                P{tp.slot}: {tp.name}
                              </option>
                            ))
                          : [1, 2, 3, 4, 5, 6].map((s) => (
                              <option key={s} value={s}>Slot P{s}</option>
                            ))}
                      </select>
                      <input
                        type="text"
                        value={o.label}
                        onChange={(e) =>
                          setOutputs((prev) => prev.map((it, i) => (i === idx ? { ...it, label: e.target.value } : it)))
                        }
                        placeholder="Label parameter"
                        className="col-span-4 text-xs rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                      />
                      <input
                        type="text"
                        value={o.unit || ''}
                        onChange={(e) =>
                          setOutputs((prev) => prev.map((it, i) => (i === idx ? { ...it, unit: e.target.value } : it)))
                        }
                        placeholder="Satuan (°C)"
                        className="col-span-2 text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                      />
                      <input
                        type="number"
                        step="any"
                        value={o.default_fallback ?? 0}
                        onChange={(e) =>
                          setOutputs((prev) => prev.map((it, i) => (i === idx ? { ...it, default_fallback: parseFloat(e.target.value) || 0 } : it)))
                        }
                        placeholder="Default"
                        title="Nilai default / fallback"
                        className="col-span-2 text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                      />
                      <button
                        type="button"
                        disabled={outputs.length <= 1}
                        onClick={() => setOutputs((prev) => prev.filter((_, i) => i !== idx))}
                        className="col-span-1 p-1 text-rose-500 hover:bg-rose-50 rounded disabled:opacity-30 flex justify-center"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 p-3 rounded-lg border border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Satuan</label>
                  <input
                    type="text"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    placeholder="L / °C / min"
                    className="w-full text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Desimal</label>
                  <select
                    value={decimalPlaces}
                    onChange={(e) => setDecimalPlaces(Number(e.target.value))}
                    className="w-full text-xs rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  >
                    <option value={0}>0 (Bulat)</option>
                    <option value={1}>1 angka</option>
                    <option value={2}>2 angka</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Batas Min</label>
                  <input
                    type="number"
                    step="any"
                    value={minValue}
                    onChange={(e) => setMinValue(e.target.value)}
                    placeholder="Bebas"
                    className="w-full text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Batas Maks</label>
                  <input
                    type="number"
                    step="any"
                    value={maxValue}
                    onChange={(e) => setMaxValue(e.target.value)}
                    placeholder="Bebas"
                    className="w-full text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Fallback Default</label>
                  <input
                    type="number"
                    step="any"
                    value={defaultFallback}
                    onChange={(e) => setDefaultFallback(e.target.value)}
                    className="w-full text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
              </div>
            )}

            {/* 3. PILIH 4 JENIS FORMULA */}
            <div className="space-y-2">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-500">
                Pilih Jenis Rumus
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {FORMULA_TYPE_TABS.map((tab) => {
                  const Icon = tab.icon;
                  const active = formulaType === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => handleSwitchType(tab.id)}
                      className={`p-2.5 rounded-lg border-2 text-left transition ${
                        active
                          ? 'border-primary bg-primary/10 text-primary shadow-xs'
                          : 'border-stroke dark:border-strokedark hover:border-gray-300 text-gray-600 dark:text-gray-300'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 text-xs font-bold">
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{tab.label}</span>
                      </div>
                      <div className="text-[10px] opacity-75 mt-0.5 truncate">{tab.desc}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* VARIABLE & OPERATOR QUICK CHIP BAR */}
            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-stroke dark:border-strokedark space-y-1.5">
              <div className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                Klik Chip Variabel / Operator untuk Menyisipkan ke Kotak Rumus:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {DEFAULT_BATCH_VARIABLES.filter((v) => v.type === 'number').map((v) => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => insertToken(v.key)}
                    className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-200 hover:bg-blue-600 hover:text-white transition"
                    title={`Sisipkan ${v.key} (${v.unit})`}
                  >
                    + {v.label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1 pt-0.5">
                {QUICK_MATH_TOKENS.map((t) => (
                  <button
                    key={t.label}
                    type="button"
                    onClick={() => insertToken(t.insert)}
                    className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-gray-200/80 dark:bg-meta-4 text-gray-800 dark:text-gray-200 hover:bg-primary hover:text-white transition"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 4. BUILDER AREA BY TYPE */}
            {formulaType === 'MATH' && (
              <div className="p-4 rounded-xl border border-blue-200 dark:border-blue-800/60 bg-blue-50/30 dark:bg-blue-950/15 space-y-3">
                <div className="text-xs font-bold text-blue-800 dark:text-blue-300">
                  Rumus Matematika Langsung
                </div>
                {renderResultInputs(
                  definition.expression ?? '',
                  (v) => setDefinition({ ...definition, expression: v }),
                  definition.expressions || {},
                  (k, v) =>
                    setDefinition({
                      ...definition,
                      expressions: { ...(definition.expressions || {}), [k]: v },
                    })
                )}
              </div>
            )}

            {formulaType === 'IF_ELSE' && (
              <div className="space-y-3">
                {(definition.rules || []).map((rule, rIdx) => {
                  const isMatched = simResult.ok && simResult.matched_rule_index === rIdx;
                  return (
                    <div
                      key={rIdx}
                      className={`p-3.5 rounded-xl border-2 space-y-2.5 transition ${
                        isMatched
                          ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20'
                          : 'border-purple-200 dark:border-purple-800/60 bg-purple-50/20 dark:bg-purple-950/10'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-purple-600 text-white">
                            {rIdx === 0 ? 'JIKA (IF)' : `ELSE IF #${rIdx + 1}`}
                          </span>
                          <input
                            type="text"
                            value={rule.label || ''}
                            onChange={(e) => {
                              const rules = [...(definition.rules || [])];
                              rules[rIdx] = { ...rules[rIdx], label: e.target.value };
                              setDefinition({ ...definition, rules });
                            }}
                            placeholder="Nama aturan (opsional)"
                            className="text-xs font-semibold bg-transparent border-b border-dashed border-gray-300 dark:border-gray-600 text-black dark:text-white outline-none focus:border-primary"
                          />
                          {isMatched && (
                            <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="h-3.5 w-3.5" /> Cocok di Simulator
                            </span>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            const rules = (definition.rules || []).filter((_, i) => i !== rIdx);
                            setDefinition({ ...definition, rules });
                          }}
                          className="text-rose-500 hover:bg-rose-50 p-1 rounded"
                          title="Hapus kondisi"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {/* Conditions list */}
                      <div className="space-y-2 pl-2 border-l-2 border-purple-300 dark:border-purple-700">
                        {(rule.conditions || []).map((cond, cIdx) => {
                          const isNum = NUMERIC_VAR_KEYS.has(cond.var);
                          const ops = isNum ? NUMERIC_OPERATORS : TEXT_OPERATORS;
                          return (
                            <div key={cIdx} className="flex flex-wrap items-center gap-1.5">
                              {cIdx > 0 && (
                                <select
                                  value={rule.logic || 'AND'}
                                  onChange={(e) => {
                                    const rules = [...(definition.rules || [])];
                                    rules[rIdx] = { ...rules[rIdx], logic: e.target.value };
                                    setDefinition({ ...definition, rules });
                                  }}
                                  className="text-[10px] font-black rounded bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-200 px-1.5 py-1"
                                >
                                  <option value="AND">DAN</option>
                                  <option value="OR">ATAU</option>
                                </select>
                              )}
                              <select
                                value={cond.var}
                                onChange={(e) => {
                                  const newVar = e.target.value;
                                  const newIsNum = NUMERIC_VAR_KEYS.has(newVar);
                                  const rules = [...(definition.rules || [])];
                                  const conds = [...(rules[rIdx].conditions || [])];
                                  conds[cIdx] = {
                                    ...conds[cIdx],
                                    var: newVar,
                                    op: newIsNum ? '>' : 'equals',
                                    value: newIsNum ? 0 : '',
                                  };
                                  rules[rIdx] = { ...rules[rIdx], conditions: conds };
                                  setDefinition({ ...definition, rules });
                                }}
                                className="text-xs font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                              >
                                <optgroup label="Fisik & Kapasitas (Angka)">
                                  {DEFAULT_BATCH_VARIABLES.filter((v) => v.type === 'number').map((v) => (
                                    <option key={v.key} value={v.key}>
                                      {v.label} ({v.unit})
                                    </option>
                                  ))}
                                </optgroup>
                                <optgroup label="Kain, Warna & Proses">
                                  {DEFAULT_BATCH_VARIABLES.filter((v) => v.type !== 'number').map((v) => (
                                    <option key={v.key} value={v.key}>
                                      {v.label}
                                    </option>
                                  ))}
                                </optgroup>
                              </select>

                              <select
                                value={cond.op}
                                onChange={(e) => {
                                  const rules = [...(definition.rules || [])];
                                  const conds = [...(rules[rIdx].conditions || [])];
                                  conds[cIdx] = { ...conds[cIdx], op: e.target.value };
                                  rules[rIdx] = { ...rules[rIdx], conditions: conds };
                                  setDefinition({ ...definition, rules });
                                }}
                                className="text-xs rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                              >
                                {ops.map((o) => (
                                  <option key={o.value} value={o.value}>{o.label}</option>
                                ))}
                              </select>

                              {renderConditionValueInput(cond, (newVal) => {
                                const rules = [...(definition.rules || [])];
                                const conds = [...(rules[rIdx].conditions || [])];
                                conds[cIdx] = { ...conds[cIdx], value: newVal };
                                rules[rIdx] = { ...rules[rIdx], conditions: conds };
                                setDefinition({ ...definition, rules });
                              })}

                              {cond.op === 'between' && (
                                <input
                                  type="number"
                                  step="any"
                                  value={cond.value2 ?? ''}
                                  onChange={(e) => {
                                    const rules = [...(definition.rules || [])];
                                    const conds = [...(rules[rIdx].conditions || [])];
                                    conds[cIdx] = { ...conds[cIdx], value2: e.target.value };
                                    rules[rIdx] = { ...rules[rIdx], conditions: conds };
                                    setDefinition({ ...definition, rules });
                                  }}
                                  placeholder="Maks"
                                  className="w-20 text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                                />
                              )}

                              {(rule.conditions || []).length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const rules = [...(definition.rules || [])];
                                    rules[rIdx] = {
                                      ...rules[rIdx],
                                      conditions: rules[rIdx].conditions.filter((_, i) => i !== cIdx),
                                    };
                                    setDefinition({ ...definition, rules });
                                  }}
                                  className="text-gray-400 hover:text-rose-500 p-1"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          );
                        })}

                        <button
                          type="button"
                          onClick={() => {
                            const rules = [...(definition.rules || [])];
                            rules[rIdx] = {
                              ...rules[rIdx],
                              conditions: [
                                ...(rules[rIdx].conditions || []),
                                { var: 'fabric_weight_kg', op: '>', value: 200 },
                              ],
                            };
                            setDefinition({ ...definition, rules });
                          }}
                          className="text-[11px] font-bold text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1"
                        >
                          <Plus className="h-3 w-3" /> Tambah Syarat (DAN / ATAU)
                        </button>
                      </div>

                      {/* THEN Result */}
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2 border-t border-purple-200/70 dark:border-purple-800/50">
                        <span className="shrink-0 text-[11px] font-black text-indigo-700 dark:text-indigo-300">
                          → MAKA HASIL:
                        </span>
                        {renderResultInputs(
                          rule.result_expr ?? '',
                          (v) => {
                            const rules = [...(definition.rules || [])];
                            rules[rIdx] = { ...rules[rIdx], result_expr: v };
                            setDefinition({ ...definition, rules });
                          },
                          rule.outputs || {},
                          (k, v) => {
                            const rules = [...(definition.rules || [])];
                            rules[rIdx] = { ...rules[rIdx], outputs: { ...(rules[rIdx].outputs || {}), [k]: v } };
                            setDefinition({ ...definition, rules });
                          }
                        )}
                      </div>
                    </div>
                  );
                })}

                <button
                  type="button"
                  onClick={() => {
                    const rules = [
                      ...(definition.rules || []),
                      {
                        label: `Kondisi ${(definition.rules || []).length + 1}`,
                        logic: 'AND',
                        conditions: [{ var: 'fabric_weight_kg', op: '>', value: 300 }],
                        result_expr: '0',
                        outputs: Object.fromEntries(outputs.map((o) => [o.key, '0'])),
                      },
                    ];
                    setDefinition({ ...definition, rules });
                  }}
                  className="w-full py-2 rounded-lg border-2 border-dashed border-purple-300 dark:border-purple-700 text-xs font-bold text-purple-700 dark:text-purple-300 hover:bg-purple-50 dark:hover:bg-purple-950/30 transition flex items-center justify-center gap-1.5"
                >
                  <Plus className="h-4 w-4" /> Tambah Kondisi Lain (ELSE IF)
                </button>

                {/* ELSE / DEFAULT */}
                <div
                  className={`p-3.5 rounded-xl border-2 space-y-2 ${
                    simResult.ok && simResult.matched_rule_index === -1
                      ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20'
                      : 'border-gray-300 dark:border-gray-700 bg-gray-50/70 dark:bg-meta-4/30'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-gray-700 text-white">
                      SELAIN ITU (ELSE / DEFAULT)
                    </span>
                    {simResult.ok && simResult.matched_rule_index === -1 && (
                      <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Dipakai di Simulator
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                    <span className="shrink-0 text-[11px] font-bold text-gray-600 dark:text-gray-300">→ HASIL DEFAULT:</span>
                    {renderResultInputs(
                      definition.else_expr ?? '',
                      (v) => setDefinition({ ...definition, else_expr: v }),
                      definition.else_outputs || {},
                      (k, v) =>
                        setDefinition({
                          ...definition,
                          else_outputs: { ...(definition.else_outputs || {}), [k]: v },
                        })
                    )}
                  </div>
                </div>
              </div>
            )}

            {formulaType === 'RANGE_TABLE' && (
              <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-800/60 bg-amber-50/25 dark:bg-amber-950/10 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-black dark:text-white">Variabel Rentang:</span>
                    <select
                      value={definition.input_var || 'fabric_weight_kg'}
                      onChange={(e) => setDefinition({ ...definition, input_var: e.target.value })}
                      className="text-xs font-bold rounded border border-amber-300 dark:border-amber-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-black dark:text-white"
                    >
                      {DEFAULT_BATCH_VARIABLES.filter((v) => v.type === 'number').map((v) => (
                        <option key={v.key} value={v.key}>
                          {v.label} ({v.unit})
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const rows = [
                        ...(definition.rows || []),
                        { min: 0, max: null, result_expr: '0', outputs: Object.fromEntries(outputs.map((o) => [o.key, '0'])), label: '' },
                      ];
                      setDefinition({ ...definition, rows });
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded bg-amber-600 text-white hover:bg-amber-700"
                  >
                    <Plus className="h-3.5 w-3.5" /> Tambah Baris
                  </button>
                </div>

                <div className="space-y-2">
                  {(definition.rows || []).map((row, idx) => {
                    const isMatched = simResult.ok && simResult.matched_rule_index === idx;
                    return (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-lg border flex flex-col gap-2 ${
                          isMatched
                            ? 'border-emerald-500 bg-emerald-50/70 dark:bg-emerald-950/25'
                            : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark'
                        }`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[10px] font-bold text-gray-500">Dari (≥):</span>
                          <input
                            type="number"
                            step="any"
                            value={row.min ?? ''}
                            onChange={(e) => {
                              const rows = [...(definition.rows || [])];
                              rows[idx] = { ...rows[idx], min: e.target.value === '' ? null : Number(e.target.value) };
                              setDefinition({ ...definition, rows });
                            }}
                            placeholder="-∞"
                            className="w-24 text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-transparent px-2 py-1 text-black dark:text-white"
                          />
                          <span className="text-[10px] font-bold text-gray-500">Sampai (≤):</span>
                          <input
                            type="number"
                            step="any"
                            value={row.max ?? ''}
                            onChange={(e) => {
                              const rows = [...(definition.rows || [])];
                              rows[idx] = { ...rows[idx], max: e.target.value === '' ? null : Number(e.target.value) };
                              setDefinition({ ...definition, rows });
                            }}
                            placeholder="∞ (Tak terbatas)"
                            className="w-28 text-xs font-mono rounded border border-stroke dark:border-gray-700 bg-transparent px-2 py-1 text-black dark:text-white"
                          />
                          <input
                            type="text"
                            value={row.label || ''}
                            onChange={(e) => {
                              const rows = [...(definition.rows || [])];
                              rows[idx] = { ...rows[idx], label: e.target.value };
                              setDefinition({ ...definition, rows });
                            }}
                            placeholder="Label (mis. Lot Besar)"
                            className="flex-1 min-w-[110px] text-xs rounded border border-stroke dark:border-gray-700 bg-transparent px-2 py-1 text-black dark:text-white"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              const rows = (definition.rows || []).filter((_, i) => i !== idx);
                              setDefinition({ ...definition, rows });
                            }}
                            className="text-rose-500 hover:bg-rose-50 p-1 rounded"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-black text-indigo-700 dark:text-indigo-300 shrink-0">→ HASIL:</span>
                          {renderResultInputs(
                            row.result_expr ?? '',
                            (v) => {
                              const rows = [...(definition.rows || [])];
                              rows[idx] = { ...rows[idx], result_expr: v };
                              setDefinition({ ...definition, rows });
                            },
                            row.outputs || {},
                            (k, v) => {
                              const rows = [...(definition.rows || [])];
                              rows[idx] = { ...rows[idx], outputs: { ...(rows[idx].outputs || {}), [k]: v } };
                              setDefinition({ ...definition, rows });
                            },
                            true
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Default outside range */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2 border-t border-amber-200 dark:border-amber-800/60">
                  <span className="text-[11px] font-bold text-gray-600 dark:text-gray-300 shrink-0">Default (Di luar rentang):</span>
                  {renderResultInputs(
                    definition.default_expr ?? '',
                    (v) => setDefinition({ ...definition, default_expr: v }),
                    definition.default_outputs || {},
                    (k, v) =>
                      setDefinition({
                        ...definition,
                        default_outputs: { ...(definition.default_outputs || {}), [k]: v },
                      }),
                    true
                  )}
                </div>
              </div>
            )}

            {formulaType === 'LOOKUP_TABLE' && (
              <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/25 dark:bg-emerald-950/10 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-black dark:text-white">Petakan Berdasarkan:</span>
                    <select
                      value={definition.input_var || 'fabric_type'}
                      onChange={(e) => setDefinition({ ...definition, input_var: e.target.value })}
                      className="text-xs font-bold rounded border border-emerald-300 dark:border-emerald-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-black dark:text-white"
                    >
                      {DEFAULT_BATCH_VARIABLES.filter((v) => v.type !== 'number').map((v) => (
                        <option key={v.key} value={v.key}>
                          {v.label}
                        </option>
                      ))}
                    </select>
                    <select
                      value={definition.match_mode || 'contains'}
                      onChange={(e) => setDefinition({ ...definition, match_mode: e.target.value })}
                      className="text-xs rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                    >
                      <option value="contains">Mengandung kata (fleksibel)</option>
                      <option value="equals">Sama persis (Exact)</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const rows = [
                        ...(definition.rows || []),
                        { match_values: '', match_mode: definition.match_mode || 'contains', result_expr: '0', outputs: Object.fromEntries(outputs.map((o) => [o.key, '0'])), label: '' },
                      ];
                      setDefinition({ ...definition, rows });
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded bg-emerald-600 text-white hover:bg-emerald-700"
                  >
                    <Plus className="h-3.5 w-3.5" /> Tambah Baris
                  </button>
                </div>

                {/* Quick suggestion dropdown for category variable */}
                {(() => {
                  const varMeta = DEFAULT_BATCH_VARIABLES.find((v) => v.key === (definition.input_var || 'fabric_type'));
                  return (
                    <div className="space-y-2">
                      {(definition.rows || []).map((row, idx) => {
                        const isMatched = simResult.ok && simResult.matched_rule_index === idx;
                        return (
                          <div
                            key={idx}
                            className={`p-2.5 rounded-lg border flex flex-col gap-2 ${
                              isMatched
                                ? 'border-emerald-500 bg-emerald-50/70 dark:bg-emerald-950/30'
                                : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark'
                            }`}
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              {varMeta?.options && (
                                <select
                                  value=""
                                  onChange={(e) => {
                                    if (!e.target.value) return;
                                    const rows = [...(definition.rows || [])];
                                    const cur = (rows[idx].match_values || '').trim();
                                    rows[idx] = {
                                      ...rows[idx],
                                      match_values: cur ? `${cur}, ${e.target.value}` : e.target.value,
                                    };
                                    setDefinition({ ...definition, rows });
                                  }}
                                  className="text-[11px] font-semibold rounded border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-1 text-emerald-800 dark:text-emerald-200"
                                >
                                  <option value="">+ Pilih {varMeta.label}...</option>
                                  {varMeta.options.map((opt) => (
                                    <option key={opt} value={opt}>
                                      {varMeta.option_labels?.[opt] || opt}
                                    </option>
                                  ))}
                                </select>
                              )}
                              <input
                                type="text"
                                value={row.match_values || ''}
                                onChange={(e) => {
                                  const rows = [...(definition.rows || [])];
                                  rows[idx] = { ...rows[idx], match_values: e.target.value };
                                  setDefinition({ ...definition, rows });
                                }}
                                placeholder="Kata kunci (pisahkan koma, mis. POLYESTER, PES)"
                                className="flex-1 min-w-[160px] text-xs font-bold rounded border border-stroke dark:border-gray-700 bg-transparent px-2 py-1 text-black dark:text-white"
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const rows = (definition.rows || []).filter((_, i) => i !== idx);
                                  setDefinition({ ...definition, rows });
                                }}
                                className="text-rose-500 hover:bg-rose-50 p-1 rounded"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-black text-indigo-700 dark:text-indigo-300 shrink-0">→ HASIL:</span>
                              {renderResultInputs(
                                row.result_expr ?? '',
                                (v) => {
                                  const rows = [...(definition.rows || [])];
                                  rows[idx] = { ...rows[idx], result_expr: v };
                                  setDefinition({ ...definition, rows });
                                },
                                row.outputs || {},
                                (k, v) => {
                                  const rows = [...(definition.rows || [])];
                                  rows[idx] = { ...rows[idx], outputs: { ...(rows[idx].outputs || {}), [k]: v } };
                                  setDefinition({ ...definition, rows });
                                },
                                true
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}

                <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2 border-t border-emerald-200 dark:border-emerald-800/60">
                  <span className="text-[11px] font-bold text-gray-600 dark:text-gray-300 shrink-0">Lainnya (Default):</span>
                  {renderResultInputs(
                    definition.default_expr ?? '',
                    (v) => setDefinition({ ...definition, default_expr: v }),
                    definition.default_outputs || {},
                    (k, v) =>
                      setDefinition({
                        ...definition,
                        default_outputs: { ...(definition.default_outputs || {}), [k]: v },
                      }),
                    true
                  )}
                </div>
              </div>
            )}

            {/* RINGKASAN KALIMAT NATURAL */}
            <div className="p-3 rounded-lg bg-gray-100/80 dark:bg-meta-4/50 border border-stroke dark:border-strokedark text-xs text-gray-700 dark:text-gray-200 flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Ringkasan Aturan: </span>
                <span>{humanSummary}</span>
              </div>
            </div>

            {/* PENGIRIMAN CEPAT KE GRUP MESIN & PER MESIN */}
            <div className="p-3.5 rounded-lg border border-stroke dark:border-strokedark space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-black dark:text-white flex items-center gap-1.5">
                  <Globe className="h-4 w-4 text-emerald-600" />
                  Kirim Formula ke Grup Mesin / Per Mesin:
                </span>
                <label className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 dark:text-emerald-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={applyAllGroups}
                    onChange={(e) => setApplyAllGroups(e.target.checked)}
                    className="accent-emerald-600"
                  />
                  <span>Semua Grup & Mesin</span>
                </label>
              </div>
              {!applyAllGroups && (
                <div className="space-y-2.5">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1">
                      Per Grup Mesin ({selectedGroups.length} dipilih):
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {machineGroups.map((grp) => {
                        const checked = selectedGroups.includes(grp.group_name);
                        return (
                          <button
                            key={grp.group_name}
                            type="button"
                            onClick={() =>
                              setSelectedGroups((prev) =>
                                prev.includes(grp.group_name)
                                  ? prev.filter((x) => x !== grp.group_name)
                                  : [...prev, grp.group_name]
                              )
                            }
                            className={`px-2.5 py-1 rounded-full text-[11px] font-bold border transition ${
                              checked
                                ? 'bg-primary text-white border-primary'
                                : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-gray-300 border-stroke dark:border-gray-700 hover:border-primary'
                            }`}
                          >
                            {checked ? '✓ ' : '+ '}
                            {grp.group_name} ({grp.machine_count})
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-stroke dark:border-strokedark space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                        Atau Pilih Per Mesin Spesifik ({selectedMachines.length} dipilih):
                      </span>
                      <input
                        type="text"
                        value={machineFilter}
                        onChange={(e) => setMachineFilter(e.target.value)}
                        placeholder="Cari mesin (DA01, 1B...)"
                        className="w-40 text-[11px] rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-0.5 text-black dark:text-white outline-none focus:border-primary"
                      />
                    </div>
                    <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                      {machineGroups
                        .flatMap((g) => g.machines || [])
                        .filter((m, idx, arr) => arr.findIndex((x) => x.machine_no === m.machine_no) === idx)
                        .filter((m) =>
                          !machineFilter.trim() ||
                          String(m.machine_no).toLowerCase().includes(machineFilter.trim().toLowerCase())
                        )
                        .map((m) => {
                          const checked = selectedMachines.includes(m.machine_no);
                          return (
                            <button
                              key={m.machine_no}
                              type="button"
                              onClick={() =>
                                setSelectedMachines((prev) =>
                                  prev.includes(m.machine_no)
                                    ? prev.filter((x) => x !== m.machine_no)
                                    : [...prev, m.machine_no]
                                )
                              }
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition ${
                                checked
                                  ? 'bg-cyan-600 text-white border-cyan-600'
                                  : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-gray-300 border-stroke dark:border-gray-700 hover:border-cyan-500'
                              }`}
                            >
                              {checked ? '✓ ' : '+ '}
                              {m.machine_no}
                            </button>
                          );
                        })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT: LIVE SIMULATOR (4 cols) */}
          <div className="lg:col-span-4 bg-gray-50/90 dark:bg-[#0d1624] overflow-y-auto p-4 space-y-4">
            <div className="flex items-center gap-2 border-b border-stroke dark:border-strokedark pb-2.5">
              <Play className="h-4 w-4 text-emerald-600" />
              <div>
                <h3 className="text-xs font-black uppercase tracking-wider text-black dark:text-white">
                  Simulator Uji Coba Instan
                </h3>
                <p className="text-[10px] text-gray-500">Ubah contoh input batch di bawah untuk cek hasil seketika.</p>
              </div>
            </div>

            {/* RESULT CARD */}
            <div
              className={`p-4 rounded-xl border-2 shadow-xs space-y-2 ${
                simResult.ok
                  ? 'border-emerald-500 bg-white dark:bg-boxdark'
                  : 'border-rose-500 bg-rose-50 dark:bg-rose-950/30'
              }`}
            >
              {simResult.ok ? (
                <>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                    Hasil Kalkulasi ({simResult.matched_label})
                  </div>
                  {outputMode === 'SINGLE' ? (
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-3xl font-black font-mono text-black dark:text-white tabular-nums">
                        {simResult.value}
                      </span>
                      {unit && <span className="text-sm font-bold text-gray-500">{unit}</span>}
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {Object.values(simResult.values || {}).map((item) => (
                        <div
                          key={item.key}
                          className="flex items-center justify-between text-xs py-1 border-b last:border-b-0 border-stroke dark:border-strokedark"
                        >
                          <span className="font-semibold text-gray-600 dark:text-gray-300">{item.label}</span>
                          <span className="font-mono font-black text-emerald-600 dark:text-emerald-400">
                            {item.value} {item.unit}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {simResult.clamped && (
                    <div className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" /> Nilai dibatasi ke rentang aman Min/Maks.
                    </div>
                  )}
                </>
              ) : (
                <div className="text-xs font-bold text-rose-600 dark:text-rose-400 flex items-start gap-1.5">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{simResult.error}</span>
                </div>
              )}
            </div>

            {/* SIMULATOR INPUTS (DROPDOWN + ANGKA) */}
            <div className="space-y-2.5 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Berat Kain (kg)</label>
                  <input
                    type="number"
                    value={simCtx.fabric_weight_kg}
                    onChange={(e) => setSimCtx({ ...simCtx, fabric_weight_kg: Number(e.target.value) })}
                    className="w-full font-mono font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Liquor Ratio (1:x)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={simCtx.liquor_ratio}
                    onChange={(e) => setSimCtx({ ...simCtx, liquor_ratio: Number(e.target.value) })}
                    className="w-full font-mono font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Jenis Kain / Serat</label>
                  <select
                    value={simCtx.fabric_type}
                    onChange={(e) => setSimCtx({ ...simCtx, fabric_type: e.target.value })}
                    className="w-full font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  >
                    {FABRIC_TYPE_OPTIONS.map((ft) => (
                      <option key={ft} value={ft}>{ft}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Kedalaman Warna</label>
                  <select
                    value={simCtx.color_shade}
                    onChange={(e) => setSimCtx({ ...simCtx, color_shade: e.target.value })}
                    className="w-full font-bold rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  >
                    {COLOR_SHADE_OPTIONS.map((sh) => (
                      <option key={sh} value={sh}>{sh}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Jenis Zat Warna</label>
                  <select
                    value={simCtx.dye_type}
                    onChange={(e) => setSimCtx({ ...simCtx, dye_type: e.target.value })}
                    className="w-full rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  >
                    {DYE_TYPE_OPTIONS.map((dt) => (
                      <option key={dt} value={dt}>{dt}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Status Redye</label>
                  <select
                    value={simCtx.redye}
                    onChange={(e) => setSimCtx({ ...simCtx, redye: e.target.value })}
                    className="w-full rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-black dark:text-white"
                  >
                    <option value="0">Normal (0)</option>
                    <option value="1">Redye (1)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">GSM</label>
                  <input
                    type="number"
                    value={simCtx.fabric_gsm}
                    onChange={(e) => setSimCtx({ ...simCtx, fabric_gsm: Number(e.target.value) })}
                    className="w-full font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Panjang (m)</label>
                  <input
                    type="number"
                    value={simCtx.fabric_length}
                    onChange={(e) => setSimCtx({ ...simCtx, fabric_length: Number(e.target.value) })}
                    className="w-full font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Kap. Mesin</label>
                  <input
                    type="number"
                    value={simCtx.machine_capacity_kg}
                    onChange={(e) => setSimCtx({ ...simCtx, machine_capacity_kg: Number(e.target.value) })}
                    className="w-full font-mono rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-gray-500 mb-0.5">Artikel Kain</label>
                <input
                  type="text"
                  value={simCtx.article}
                  onChange={(e) => setSimCtx({ ...simCtx, article: e.target.value })}
                  className="w-full rounded border border-stroke dark:border-gray-700 bg-white dark:bg-slate-900 px-2 py-1 text-black dark:text-white"
                />
              </div>

              <div className="p-2 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-[10px] text-gray-500 flex justify-between">
                <span>Total Air: <strong className="font-mono text-black dark:text-white">{(simCtx.fabric_weight_kg * simCtx.liquor_ratio).toFixed(0)} L</strong></span>
                <span>Beban Mesin: <strong className="font-mono text-black dark:text-white">{simCtx.machine_capacity_kg > 0 ? ((simCtx.fabric_weight_kg / simCtx.machine_capacity_kg) * 100).toFixed(0) : 100}%</strong></span>
              </div>
            </div>
          </div>
        </div>

        {/* FOOTER */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-stroke dark:border-strokedark bg-gray-50/80 dark:bg-meta-4/30">
          <span className="text-[11px] text-gray-500">
            Formula akan otomatis divalidasi & tersedia di Program Studio sesuai Grup Mesin terpilih.
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-meta-4"
            >
              Batal
            </button>
            <button
              type="button"
              disabled={saving || !simResult.ok}
              onClick={handleSave}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 shadow-sm transition"
            >
              <Save className="h-4 w-4" />
              <span>{saving ? 'Menyimpan...' : isEditing ? 'Simpan Perubahan' : 'Simpan Formula'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
