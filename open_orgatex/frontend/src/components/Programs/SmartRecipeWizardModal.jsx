import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Wand2,
  X,
  ChevronRight,
  ChevronLeft,
  Check,
  Flame,
  Clock,
  Droplet,
  Gauge,
  Sparkles,
  Layers,
  Cpu
} from 'lucide-react';
import fallbackTypeconf from '../../data/typeconf_functions.json';
import { useToast } from '../../context/ToastContext';

// Resolve valid Function ID strictly from target machine's Config/TYPECONF.CNF (never hardcoded or from .AWL)
function resolveMachineFn(funcsMap, role) {
  const funcs = (funcsMap && Object.keys(funcsMap).length > 0) ? funcsMap : (fallbackTypeconf.functions || {});
  const vals = Object.values(funcs);
  const byId = (ids) => {
    for (const id of ids) {
      if (funcs[String(id)]) return funcs[String(id)];
    }
    return null;
  };
  const byName = (keywords, lineReq = 1) => vals.find(f => {
    const nm = (f.name || '').toLowerCase();
    const lines = Array.isArray(f.lines) ? f.lines : [];
    const lineOk = !lineReq || lines.length === 0 || lines.includes(lineReq);
    return lineOk && keywords.some(k => nm.includes(k));
  });

  switch (role) {
    case 'FILL':
      return byId([713, 722, 22, 21]) || byName(['fill level', 'fill quantity', 'fill'], 1);
    case 'DOSING_1':
      return byId([938, 733, 227, 731, 703]) || byName(['dosing', 'inject'], 1);
    case 'DOSING_2':
      return byId([939, 743, 228, 741]) || byId([938, 733, 227]) || byName(['dosing', 'inject'], 1);
    case 'TEMP':
      return byId([141, 811]) || byName(['temperature control', 'temp'], 1);
    case 'RUNTIME':
      return byId([144, 810]) || byName(['runtime', 'run time'], 1);
    case 'RINSE':
      return byId([710, 243, 720, 723, 725, 242]) || byName(['rinse'], 1);
    case 'DRAIN':
      return byId([71, 706, 705, 61]) || byName(['drain'], 1);
    case 'PUMP':
      return byId([404, 760, 771]) || byName(['pump', 'blower'], 2);
    default:
      return null;
  }
}

function makeFnEntry(fnDef, column = 1, params = []) {
  if (!fnDef) return null;
  const pCount = fnDef.parameter_count || (fnDef.parameters || []).length || 0;
  const padded = [];
  for (let i = 0; i < 6; i++) {
    if (i < params.length && params[i] !== undefined) {
      padded.push(Number(params[i]));
    } else if (i < pCount && fnDef.parameters?.[i]?.default !== undefined) {
      padded.push(Number(fnDef.parameters[i].default));
    } else {
      padded.push(0);
    }
  }
  const preferredCol = (Array.isArray(fnDef.lines) && fnDef.lines.length > 0 && !fnDef.lines.includes(column))
    ? fnDef.lines[0]
    : column;
  return {
    function_id: Number(fnDef.id),
    name: fnDef.name || fnDef.name_local || `F${fnDef.id}`,
    column: preferredCol,
    flags: 0,
    params: padded
  };
}

function buildPhaseStepsForMachine(phaseKey, funcsMap, { temp, hold, water, pump }) {
  const fFill = resolveMachineFn(funcsMap, 'FILL');
  const fDos1 = resolveMachineFn(funcsMap, 'DOSING_1');
  const fDos2 = resolveMachineFn(funcsMap, 'DOSING_2');
  const fTemp = resolveMachineFn(funcsMap, 'TEMP');
  const fRun = resolveMachineFn(funcsMap, 'RUNTIME');
  const fDrain = resolveMachineFn(funcsMap, 'DRAIN');
  const fPump = resolveMachineFn(funcsMap, 'PUMP');

  const withPump = (mainEntry, pumpPct) => {
    const arr = [mainEntry].filter(Boolean);
    if (fPump && mainEntry && mainEntry.column === 1) {
      const pEntry = makeFnEntry(fPump, 2, [30.0, pumpPct]);
      if (pEntry && pEntry.column > 1) arr.push(pEntry);
    }
    return arr;
  };

  const steps = [];
  const pushStep = (label, fns) => {
    const validFns = (fns || []).filter(Boolean);
    if (validFns.length > 0) {
      steps.push({ step_no: steps.length + 1, label, functions: validFns });
    }
  };

  if (phaseKey === 'SCOUR') {
    pushStep('Isi Air Hangat S/B', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep('Dosing Kostik & H2O2 (AT1)', [makeFnEntry(fDos1, 1, [40.0, 1.5, 0.0, 1.0, 10.0])]);
    pushStep(`Pemanasan & Tahan ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 2.5, hold])]);
    pushStep('Drain Total', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'DYE_DISP') {
    pushStep('Isi Air Celup & Pompa HT', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep('Injeksi Zat Warna Disperse', [makeFnEntry(fDos2, 1, [40.0, 1.5, 0.0, 1.0, 15.0])]);
    pushStep(`Penaikan & Tahan ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 1.8, hold])]);
    pushStep('Pendinginan ke 80°C', [makeFnEntry(fTemp, 1, [80.0, 1.8, 5.0])]);
    pushStep('Drain Larutan Celup', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'DYE_REACT') {
    pushStep('Isi Air & Sirkulasi Reaktif', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep('Injeksi Garam Glauber (AT1)', [makeFnEntry(fDos1, 1, [40.0, 1.5, 0.0, 1.0, 15.0])]);
    pushStep('Injeksi Zat Warna Reaktif (AT2)', [makeFnEntry(fDos2, 1, [40.0, 1.5, 0.0, 1.0, 20.0])]);
    pushStep(`Pemanasan & Fiksasi ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 1.5, hold])]);
    pushStep('Injeksi Alkali Soda Ash (AT1)', [makeFnEntry(fDos1, 1, [temp, 1.5, 0.0, 1.0, 20.0])]);
    pushStep('Drain Larutan Celup', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'DYE_ACID') {
    pushStep('Isi Air Celup Nilon', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep('Dosing Zat Asam & Pewarna', [makeFnEntry(fDos1, 1, [40.0, 1.5, 0.0, 1.0, 15.0])]);
    pushStep(`Penaikan & Tahan ${temp}°C Nilon`, [makeFnEntry(fTemp, 1, [temp, 2.0, hold])]);
    pushStep('Drain', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'HOT_RINSE') {
    pushStep('Isi Air Bilas Hangat', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep(`Pemanasan Bilas ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 2.5, hold])]);
    pushStep('Drain', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'SOAP') {
    pushStep('Isi Air Sabun Bersih', withPump(makeFnEntry(fFill, 1, [1.0, water]), pump));
    pushStep('Injeksi Sabun Pencuci', [makeFnEntry(fDos1, 1, [50.0, 2.0, 0.0, 1.0, 5.0])]);
    pushStep(`Pemanasan & Hold Sabun ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 3.0, hold])]);
    pushStep('Drain Panas', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'COLD_RINSE') {
    pushStep('Isi Air Dingin Akhir', [makeFnEntry(fFill, 1, [1.0, water])]);
    pushStep(`Sirkulasi Dingin ${hold}m`, withPump(makeFnEntry(fRun, 1, [hold]), pump));
    pushStep('Drain Akhir', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  } else if (phaseKey === 'SOFTENER') {
    pushStep('Isi Air Softener', [makeFnEntry(fFill, 1, [1.0, water])]);
    pushStep('Injeksi Agen Pelembut', [makeFnEntry(fDos1, 1, [40.0, 1.5, 0.0, 1.0, 8.0])]);
    pushStep(`Sirkulasi Suhu ${temp}°C`, [makeFnEntry(fTemp, 1, [temp, 2.0, hold])]);
    pushStep('Drain', [makeFnEntry(fDrain, 1, [100.0, 1.0, 0.0])]);
  }
  return steps;
}

const PRESET_FABRICS = [
  {
    id: 'POLY_130',
    name: 'Polyester 100% (Disperse HT 130°C)',
    desc: 'Pencelupan serat poliester suhu tinggi & reduksi pencucian',
    defaultTemp: 130,
    defaultHold: 45,
    defaultWater: 2800,
    defaultPump: 90,
    phases: ['SCOUR', 'DYE_DISP', 'HOT_RINSE', 'SOAP', 'COLD_RINSE']
  },
  {
    id: 'COTTON_60',
    name: 'Katun 100% (Reaktif Dingin 60°C)',
    desc: 'Pencelupan selulosa reaktif dengan garam & alkali fiksasi',
    defaultTemp: 60,
    defaultHold: 60,
    defaultWater: 3000,
    defaultPump: 85,
    phases: ['SCOUR', 'DYE_REACT', 'HOT_RINSE', 'SOAP', 'COLD_RINSE']
  },
  {
    id: 'POLY_COTTON',
    name: 'Polyester / Katun TC Blend',
    desc: 'Kombinasi proses prapengolahan, dispersi poliester dan reaktif katun',
    defaultTemp: 130,
    defaultHold: 50,
    defaultWater: 3200,
    defaultPump: 85,
    phases: ['SCOUR', 'DYE_DISP', 'HOT_RINSE', 'DYE_REACT', 'SOAP', 'COLD_RINSE']
  },
  {
    id: 'NYLON_98',
    name: 'Nylon / Polyamide (Acid 98°C)',
    desc: 'Pencelupan nilon dengan zat warna asam & leveling agent',
    defaultTemp: 98,
    defaultHold: 45,
    defaultWater: 2600,
    defaultPump: 80,
    phases: ['SCOUR', 'DYE_ACID', 'HOT_RINSE', 'COLD_RINSE']
  }
];

const PHASE_DEFINITIONS = {
  SCOUR: {
    number: 'TR-SCOUR',
    name: 'Prapengolahan S/B (Scouring & Bleaching)',
    category: 'Pretreatment',
    desc: 'Pemasakan serat kapas/kain suhu 98°C dan pengeluaran kotoran',
    temp: 98,
    hold: 35,
    water: 3200,
    steps: [
      { step_no: 1, label: 'Isi Air Hangat S/B', functions: [{ function_id: 713, column: 1, params: [1.0, 3200.0] }] },
      { step_no: 2, label: 'Dosing Kostik & H2O2', functions: [{ function_id: 85, column: 1, params: [10.0, 100.0] }, { function_id: 404, column: 2, params: [85.0] }] },
      { step_no: 3, label: 'Pemanasan ke 98°C', functions: [{ function_id: 141, column: 1, params: [98.0, 2.5] }] },
      { step_no: 4, label: 'Tahan Pemasakan 98°C', functions: [{ function_id: 121, column: 1, params: [35.0] }] },
      { step_no: 5, label: 'Drain Total', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  DYE_DISP: {
    number: 'TR-DYE-DISP',
    name: 'Pencelupan Disperse 130°C (HT Dyeing)',
    category: 'Dyeing',
    desc: 'Siklus pencelupan dispersi tekanan & suhu tinggi poliester',
    temp: 130,
    hold: 45,
    water: 2800,
    steps: [
      { step_no: 1, label: 'Isi Air Celup & Pompa HT', functions: [{ function_id: 713, column: 1, params: [1.0, 2800.0] }, { function_id: 404, column: 2, params: [90.0] }] },
      { step_no: 2, label: 'Injeksi Zat Warna Disperse', functions: [{ function_id: 86, column: 1, params: [15.0, 100.0] }] },
      { step_no: 3, label: 'Penaikan Suhu ke 130°C', functions: [{ function_id: 141, column: 1, params: [130.0, 1.8] }] },
      { step_no: 4, label: 'Tahan Pencelupan 130°C', functions: [{ function_id: 121, column: 1, params: [45.0] }] },
      { step_no: 5, label: 'Pendinginan ke 80°C', functions: [{ function_id: 144, column: 1, params: [80.0, 1.8] }] },
      { step_no: 6, label: 'Drain Larutan Celup', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  DYE_REACT: {
    number: 'TR-DYE-REACT',
    name: 'Pencelupan Reaktif Katun 60°C',
    category: 'Dyeing',
    desc: 'Pencelupan reaktif dengan garam elektrolit dan fiksasi alkali',
    temp: 60,
    hold: 60,
    water: 3000,
    steps: [
      { step_no: 1, label: 'Isi Air & Sirkulasi Reaktif', functions: [{ function_id: 713, column: 1, params: [1.0, 3000.0] }, { function_id: 404, column: 2, params: [85.0] }] },
      { step_no: 2, label: 'Injeksi Garam Glauber (AT1)', functions: [{ function_id: 85, column: 1, params: [15.0, 100.0] }] },
      { step_no: 3, label: 'Injeksi Zat Warna Reaktif (AT2)', functions: [{ function_id: 86, column: 1, params: [20.0, 100.0] }] },
      { step_no: 4, label: 'Pemanasan ke 60°C', functions: [{ function_id: 141, column: 1, params: [60.0, 1.5] }] },
      { step_no: 5, label: 'Injeksi Alkali Soda Ash', functions: [{ function_id: 85, column: 1, params: [20.0, 100.0] }] },
      { step_no: 6, label: 'Tahan Fiksasi 60°C', functions: [{ function_id: 121, column: 1, params: [60.0] }] },
      { step_no: 7, label: 'Drain Larutan Celup', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  DYE_ACID: {
    number: 'TR-DYE-ACID',
    name: 'Pencelupan Asam Nilon 98°C',
    category: 'Dyeing',
    desc: 'Pencelupan zat warna asam dengan pengontrol pH dan perataan',
    temp: 98,
    hold: 45,
    water: 2600,
    steps: [
      { step_no: 1, label: 'Isi Air Celup Nilon', functions: [{ function_id: 713, column: 1, params: [1.0, 2600.0] }, { function_id: 404, column: 2, params: [80.0] }] },
      { step_no: 2, label: 'Dosing Zat Asam & Pewarna', functions: [{ function_id: 85, column: 1, params: [15.0, 100.0] }] },
      { step_no: 3, label: 'Penaikan Suhu ke 98°C', functions: [{ function_id: 141, column: 1, params: [98.0, 2.0] }] },
      { step_no: 4, label: 'Tahan 98°C Nilon', functions: [{ function_id: 121, column: 1, params: [45.0] }] },
      { step_no: 5, label: 'Drain', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  HOT_RINSE: {
    number: 'TR-RINSE-WARM',
    name: 'Pembilasan Air Hangat 60°C',
    category: 'Rinse',
    desc: 'Pembersihan awal sisa zat kimia & garam sebelum penyabunan',
    temp: 60,
    hold: 15,
    water: 2800,
    steps: [
      { step_no: 1, label: 'Isi Air Bilas Hangat', functions: [{ function_id: 713, column: 1, params: [1.0, 2800.0] }, { function_id: 404, column: 2, params: [85.0] }] },
      { step_no: 2, label: 'Pemanasan Bilas 60°C', functions: [{ function_id: 141, column: 1, params: [60.0, 2.5] }] },
      { step_no: 3, label: 'Sirkulasi Bilas 15m', functions: [{ function_id: 144, column: 1, params: [15.0] }] },
      { step_no: 4, label: 'Drain', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  SOAP: {
    number: 'TR-SOAP',
    name: 'Pencucian Sabun Panas 95°C (Soaping)',
    category: 'Washing',
    desc: 'Pengangkatan zat warna yang tidak terfiksasi pada permukaan serat',
    temp: 95,
    hold: 20,
    water: 3000,
    steps: [
      { step_no: 1, label: 'Isi Air Sabun Bersih', functions: [{ function_id: 713, column: 1, params: [1.0, 3000.0] }, { function_id: 404, column: 2, params: [85.0] }] },
      { step_no: 2, label: 'Injeksi Sabun Pencuci', functions: [{ function_id: 85, column: 1, params: [5.0, 100.0] }] },
      { step_no: 3, label: 'Pemanasan ke 95°C', functions: [{ function_id: 141, column: 1, params: [95.0, 3.0] }] },
      { step_no: 4, label: 'Tahan Sabun 95°C', functions: [{ function_id: 121, column: 1, params: [20.0] }] },
      { step_no: 5, label: 'Drain Panas', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  COLD_RINSE: {
    number: 'TR-RINSE-COLD',
    name: 'Pembilasan Dingin Akhir',
    category: 'Rinse',
    desc: 'Penetralan suhu dan pembilasan akhir bersih sebelum bongkar kain',
    temp: 35,
    hold: 10,
    water: 2500,
    steps: [
      { step_no: 1, label: 'Isi Air Dingin Akhir', functions: [{ function_id: 713, column: 1, params: [1.0, 2500.0] }] },
      { step_no: 2, label: 'Sirkulasi Dingin 10m', functions: [{ function_id: 144, column: 1, params: [10.0] }, { function_id: 404, column: 2, params: [80.0] }] },
      { step_no: 3, label: 'Drain Akhir', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  },
  SOFTENER: {
    number: 'TR-FINISH-SOFT',
    name: 'Penyempurnaan Pelembut (Softener)',
    category: 'Finishing',
    desc: 'Pemberian pelembut katik/silikon pada suhu 45°C',
    temp: 45,
    hold: 15,
    water: 2200,
    steps: [
      { step_no: 1, label: 'Isi Air Softener', functions: [{ function_id: 713, column: 1, params: [1.0, 2200.0] }] },
      { step_no: 2, label: 'Injeksi Agen Pelembut', functions: [{ function_id: 85, column: 1, params: [8.0, 100.0] }] },
      { step_no: 3, label: 'Sirkulasi Suhu 45°C', functions: [{ function_id: 141, column: 1, params: [45.0, 2.0] }] },
      { step_no: 4, label: 'Drain', functions: [{ function_id: 71, column: 1, params: [100.0] }] }
    ]
  }
};

export default function SmartRecipeWizardModal({
  isOpen,
  onClose,
  onApplyRecipe,
  availableMachines = [],
  activeMachine = 'TD12'
}) {
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = useState(1); // 1: Profil, 2: Fasa Checklist, 3: Parameter
  const [selectedPresetId, setSelectedPresetId] = useState('POLY_130');
  const [targetMachine, setTargetMachine] = useState(activeMachine);
  const [recipeNo, setRecipeNo] = useState(201);
  const [recipeName, setRecipeName] = useState('POLYESTER DARK 130C');

  // Selected Phases (Checklist)
  const [selectedPhases, setSelectedPhases] = useState(['SCOUR', 'DYE_DISP', 'HOT_RINSE', 'SOAP', 'COLD_RINSE']);

  // Fine tune params
  const [tuningTemp, setTuningTemp] = useState(130);
  const [tuningHold, setTuningHold] = useState(45);
  const [tuningWater, setTuningWater] = useState(2800);
  const [tuningPump, setTuningPump] = useState(90);
  const [wizardMachineFuncs, setWizardMachineFuncs] = useState(fallbackTypeconf.functions || {});

  useEffect(() => {
    setTargetMachine(activeMachine);
  }, [activeMachine]);

  useEffect(() => {
    if (!isOpen || !targetMachine) return;
    let cancelled = false;
    const cleanM = targetMachine.trim().toUpperCase().replace('MESIN_', '');
    axios.get(`/api/programs/machine-workspace/${cleanM}/config`)
      .then((res) => {
        if (!cancelled && res.data?.functions && Object.keys(res.data.functions).length > 0) {
          setWizardMachineFuncs(res.data.functions);
        }
      })
      .catch(() => {
        if (!cancelled) setWizardMachineFuncs(fallbackTypeconf.functions || {});
      });
    return () => { cancelled = true; };
  }, [isOpen, targetMachine]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSelectPreset = (preset) => {
    setSelectedPresetId(preset.id);
    setSelectedPhases(preset.phases);
    setTuningTemp(preset.defaultTemp);
    setTuningHold(preset.defaultHold);
    setTuningWater(preset.defaultWater);
    setTuningPump(preset.defaultPump);
    setRecipeName(preset.name.toUpperCase().split('(')[0].trim());
  };

  const handleTogglePhase = (phaseKey) => {
    if (selectedPhases.includes(phaseKey)) {
      if (selectedPhases.length <= 1) {
        toast.warning('Resep harus memiliki minimal 1 fasa proses.');
        return;
      }
      setSelectedPhases(selectedPhases.filter(p => p !== phaseKey));
    } else {
      setSelectedPhases([...selectedPhases, phaseKey]);
    }
  };

  const handleCompileAndFinish = () => {
    // Build sub_programs array
    const subPrograms = selectedPhases.map((pKey, idx) => {
      const def = PHASE_DEFINITIONS[pKey] || {
        number: `TR-${pKey}`,
        name: `Fasa ${pKey}`,
        category: 'Process',
        steps: []
      };

      // Apply overrides if this is the main dyeing phase
      const isDyePhase = pKey.startsWith('DYE');
      const finalTemp = isDyePhase ? tuningTemp : def.temp;
      const finalHold = isDyePhase ? tuningHold : def.hold;
      const finalWater = isDyePhase ? tuningWater : def.water;

      const resolvedSteps = buildPhaseStepsForMachine(pKey, wizardMachineFuncs, {
        temp: finalTemp,
        hold: finalHold,
        water: finalWater,
        pump: tuningPump
      });

      return {
        id: idx + 1,
        position: idx + 1,
        treatment_number: def.number,
        treatment_name: def.name,
        category: def.category,
        parameters: {
          temperature: finalTemp,
          hold_time: finalHold,
          water_level: finalWater,
          pump_speed: tuningPump
        },
        steps: resolvedSteps
      };
    });

    // Build complete flattened steps array for SETEX PRG
    const flatSteps = [
      {
        step_no: 1,
        label: 'Program Start (Mulai Siklus Mesin)',
        functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }]
      }
    ];

    let stepCounter = 2;
    subPrograms.forEach(sub => {
      (sub.steps || []).forEach(st => {
        flatSteps.push({
          step_no: stepCounter++,
          label: st.label || `${sub.treatment_name} (Langkah)`,
          functions: st.functions || []
        });
      });
    });

    flatSteps.push({
      step_no: stepCounter,
      label: 'Program End (Selesai Siklus)',
      functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }]
    });

    onApplyRecipe({
      program_no: recipeNo,
      program_name: recipeName.trim().toUpperCase() || `PROGRAM #${recipeNo}`,
      machine_code: targetMachine,
      sub_programs: subPrograms,
      steps: flatSteps
    });

    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Wizard Pembuat Program Cepat"
      onClick={onClose}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white dark:bg-boxdark rounded-2xl border border-stroke dark:border-strokedark shadow-2xl max-w-2xl w-full flex flex-col max-h-[90vh] overflow-hidden"
      >
        
        {/* Wizard Header */}
        <div className="flex items-center justify-between p-5 border-b border-stroke dark:border-strokedark bg-gradient-to-r from-purple-900 via-indigo-900 to-slate-900 text-white">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-white/10 text-white rounded-xl">
              <Wand2 className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold flex items-center gap-2">
                <span>Wizard Pembuat Program Cepat</span>
                <span className="text-[10px] bg-purple-500/30 text-purple-200 border border-purple-400/30 font-bold px-2 py-0.5 rounded-full font-mono">
                  3 Langkah Kilat
                </span>
              </h3>
              <p className="text-xs text-purple-200 mt-0.5">
                Susun resep celup dan seluruh sub-programnya secara otomatis dalam 30 detik
              </p>
            </div>
          </div>

          <button onClick={onClose} className="text-purple-200 hover:text-white transition">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Stepper Steps Tracker */}
        <div className="grid grid-cols-3 border-b border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20 text-xs font-semibold">
          <div className={`py-3 px-4 text-center border-r border-stroke dark:border-strokedark ${currentStep === 1 ? 'text-primary font-bold bg-white dark:bg-boxdark' : 'text-gray-400'}`}>
            1. Profil Kain & Mesin
          </div>
          <div className={`py-3 px-4 text-center border-r border-stroke dark:border-strokedark ${currentStep === 2 ? 'text-primary font-bold bg-white dark:bg-boxdark' : 'text-gray-400'}`}>
            2. Pilihan Fasa / Sub
          </div>
          <div className={`py-3 px-4 text-center ${currentStep === 3 ? 'text-primary font-bold bg-white dark:bg-boxdark' : 'text-gray-400'}`}>
            3. Parameter Kunci
          </div>
        </div>

        {/* Wizard Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {/* STEP 1: Profil Kain & Mesin */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-black dark:text-white mb-2">
                  Pilih Karakter Kain & Metode Pencelupan:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {PRESET_FABRICS.map(preset => {
                    const isSelected = selectedPresetId === preset.id;
                    return (
                      <div
                        key={preset.id}
                        onClick={() => handleSelectPreset(preset)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition ${
                          isSelected
                            ? 'border-primary bg-primary/5 dark:bg-primary/10 shadow-xs ring-1 ring-primary'
                            : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-50 dark:hover:bg-meta-4/40'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="text-xs font-bold text-black dark:text-white">
                            {preset.name}
                          </h4>
                          {isSelected && <Check className="h-4 w-4 text-primary" />}
                        </div>
                        <p className="text-[11px] text-gray-400">
                          {preset.desc}
                        </p>
                        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-stroke/60 dark:border-strokedark/60 text-[10px] font-mono text-gray-500">
                          <span>Suhu: {preset.defaultTemp}°C</span>
                          <span>•</span>
                          <span>Tahan: {preset.defaultHold}m</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-stroke dark:border-strokedark">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 uppercase mb-1">
                    Mesin Target:
                  </label>
                  <select
                    value={targetMachine}
                    onChange={(e) => setTargetMachine(e.target.value)}
                    className="w-full text-xs font-bold font-mono rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 p-2 text-black dark:text-white outline-none"
                  >
                    {availableMachines.map(m => (
                      <option key={m.machine_no} value={m.machine_no}>
                        Mesin {m.machine_no}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 uppercase mb-1">
                    Nomor ID Resep:
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="9999"
                    value={recipeNo}
                    onChange={(e) => setRecipeNo(parseInt(e.target.value, 10) || 1)}
                    className="w-full text-xs font-bold font-mono rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 p-2 text-black dark:text-white outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 uppercase mb-1">
                    Nama Resep:
                  </label>
                  <input
                    type="text"
                    value={recipeName}
                    onChange={(e) => setRecipeName(e.target.value.toUpperCase())}
                    className="w-full text-xs font-bold uppercase rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 p-2 text-black dark:text-white outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Pilihan Fasa / Sub-Program Checklist */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-black dark:text-white mb-1">
                  Pilih Rangkaian Sub-Program (Fasa) yang Diinginkan:
                </label>
                <p className="text-xs text-gray-400 mb-3">
                  Centang modul fasa yang akan dijalankan oleh mesin. Anda dapat menambah atau mengurangi fasa sesuai kebutuhan.
                </p>

                <div className="space-y-2">
                  {Object.entries(PHASE_DEFINITIONS).map(([pKey, pDef]) => {
                    const isChecked = selectedPhases.includes(pKey);
                    return (
                      <label
                        key={pKey}
                        className={`flex items-start justify-between p-3 rounded-xl border cursor-pointer transition ${
                          isChecked
                            ? 'border-primary bg-primary/5 dark:bg-primary/10'
                            : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-50 dark:hover:bg-meta-4/30'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleTogglePhase(pKey)}
                            className="mt-1 h-4 w-4 text-primary rounded border-gray-300 focus:ring-0 cursor-pointer"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-black dark:text-white">
                                {pDef.name}
                              </span>
                              <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300">
                                {pDef.number}
                              </span>
                            </div>
                            <p className="text-[11px] text-gray-400 mt-0.5">
                              {pDef.desc}
                            </p>
                          </div>
                        </div>

                        <div className="text-right text-[11px] font-mono text-gray-500 shrink-0 pl-2">
                          <div>{pDef.temp}°C</div>
                          <div>{pDef.hold} min</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Parameter Kunci Pencelupan */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-black dark:text-white mb-1">
                  Atur Parameter Utama Siklus Pencelupan:
                </label>
                <p className="text-xs text-gray-400 mb-4">
                  Parameter ini akan langsung diinjeksikan ke dalam langkah mikro fasa pencelupan.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Suhu Target */}
                <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                      <Flame className="h-4 w-4" />
                      Suhu Puncak (°C)
                    </span>
                    <span className="font-mono text-black dark:text-white">{tuningTemp} °C</span>
                  </div>
                  <input
                    type="range"
                    min="30"
                    max="140"
                    step="1"
                    value={tuningTemp}
                    onChange={(e) => setTuningTemp(Number(e.target.value))}
                    className="w-full accent-rose-600"
                  />
                </div>

                {/* Waktu Tahan */}
                <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-orange-600 dark:text-orange-400">
                      <Clock className="h-4 w-4" />
                      Waktu Tahan Suhu (Menit)
                    </span>
                    <span className="font-mono text-black dark:text-white">{tuningHold} m</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="120"
                    step="5"
                    value={tuningHold}
                    onChange={(e) => setTuningHold(Number(e.target.value))}
                    className="w-full accent-orange-600"
                  />
                </div>

                {/* Level Air */}
                <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
                      <Droplet className="h-4 w-4" />
                      Volume Air (Liter)
                    </span>
                    <span className="font-mono text-black dark:text-white">{tuningWater} L</span>
                  </div>
                  <input
                    type="range"
                    min="500"
                    max="5000"
                    step="100"
                    value={tuningWater}
                    onChange={(e) => setTuningWater(Number(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                </div>

                {/* Kecepatan Pompa */}
                <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                      <Gauge className="h-4 w-4" />
                      Kecepatan Pompa Utama (%)
                    </span>
                    <span className="font-mono text-black dark:text-white">{tuningPump} %</span>
                  </div>
                  <input
                    type="range"
                    min="40"
                    max="100"
                    step="5"
                    value={tuningPump}
                    onChange={(e) => setTuningPump(Number(e.target.value))}
                    className="w-full accent-amber-600"
                  />
                </div>
              </div>

              {/* Ringkasan Akhir */}
              <div className="p-4 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-xs space-y-1">
                <span className="font-bold text-indigo-900 dark:text-indigo-200 block">
                  Ringkasan Pembuatan Resep:
                </span>
                <p className="text-indigo-700 dark:text-indigo-300">
                  Resep <strong>{recipeName}</strong> (M_{String(recipeNo).padStart(4, '0')}.PRG) untuk <strong>Mesin {targetMachine}</strong> akan dibuat dengan <strong>{selectedPhases.length} Sub-Program</strong> dan sekitar <strong>{selectedPhases.length * 4 + 2} Langkah Mikro</strong> otomatis.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer Navigation */}
        <div className="p-4 border-t border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/20 flex items-center justify-between">
          {currentStep > 1 ? (
            <button
              type="button"
              onClick={() => setCurrentStep(currentStep - 1)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-200 dark:bg-meta-4 text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-300 transition"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Sebelumnya</span>
            </button>
          ) : (
            <div />
          )}

          {currentStep < 3 ? (
            <button
              type="button"
              onClick={() => setCurrentStep(currentStep + 1)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-bold shadow-xs transition"
            >
              <span>Lanjut ke Langkah {currentStep + 1}</span>
              <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCompileAndFinish}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md transition active:scale-95"
            >
              <Sparkles className="h-4 w-4" />
              <span>Selesai & Buat Resep Sekarang</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
