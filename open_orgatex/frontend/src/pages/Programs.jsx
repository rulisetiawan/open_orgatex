import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Plus, 
  Trash2, 
  ArrowUp, 
  ArrowDown, 
  Save, 
  FileCode, 
  Search, 
  Copy, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  Clock,
  Droplet,
  Flame,
  Gauge,
  Sliders,
  ChevronRight,
  Sparkles,
  ArrowLeft,
  Edit3,
  Boxes,
  Download,
  Upload,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

import TempCurveChart from '../components/Charts/TempCurveChart';
import typeconfData from '../data/typeconf_functions.json';

// Helper function definitions from TYPECONF
const ALL_FUNCTIONS = typeconfData.functions || {};
const ALL_PARAMETERS = typeconfData.parameters || {};

// Common function categories for colors
const getFunctionMeta = (funcId) => {
  const f = ALL_FUNCTIONS[String(funcId)];
  const name = f?.name || `Fungsi #${funcId}`;
  
  if (funcId === 1) {
    return { name: 'Program Start', code: 'F1', color: 'border-emerald-600 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300', icon: FileCode };
  }
  if (funcId === 2) {
    return { name: 'Program End', code: 'F2', color: 'border-slate-600 bg-slate-50 text-slate-700 dark:bg-slate-900/60 dark:text-slate-300', icon: FileCode };
  }
  if (funcId === 141) {
    return { name: 'Temperature Control', code: 'F141', color: 'border-red-500 bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300', icon: Flame };
  }
  if (funcId === 713) {
    return { name: 'Water Fill (Fill Level)', code: 'F713', color: 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300', icon: Droplet };
  }
  if (funcId === 71) {
    return { name: 'Drain Percent', code: 'F71', color: 'border-cyan-600 bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300', icon: Droplet };
  }
  if (funcId === 404) {
    return { name: 'Dye Liquor Pump', code: 'F404', color: 'border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300', icon: Gauge };
  }
  if (funcId === 712) {
    return { name: 'Material Flow (Winch)', code: 'F712', color: 'border-purple-500 bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300', icon: Sliders };
  }
  if (funcId === 126 || funcId === 122) {
    return { name: name, code: `F${funcId}`, color: 'border-orange-500 bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300', icon: Clock };
  }
  return { name, code: `F${funcId}`, color: 'border-gray-400 bg-gray-50 text-gray-700 dark:bg-meta-4 dark:text-gray-300', icon: Boxes };
};

// Popular functions to choose as Main Function
const POPULAR_MAIN_FUNCTIONS = [
  { id: 141, name: 'Temperature Control (Penaikan/Penahanan Suhu)' },
  { id: 713, name: 'Fill Level (Pengisian Air Bejana Mesin)' },
  { id: 71, name: 'Drain Percent (Pembuangan Air)' },
  { id: 126, name: 'Check (Operator Check / Ambil Sampel)' },
  { id: 122, name: 'Unload (Bongkar Kain)' },
  { id: 261, name: 'Load (Muat Kain)' },
  { id: 747, name: 'Rinsing / Cooling (Bilas / Pendinginan)' },
  { id: 144, name: 'Runtime (Penahanan Waktu)' },
  { id: 938, name: 'Dosing Progression 1 (Injeksi Dosis Obat 1)' },
  { id: 939, name: 'Dosing Progression 2 (Injeksi Dosis Obat 2)' }
];

// Popular parallel functions
const POPULAR_PARALLEL_FUNCTIONS = [
  { id: 404, col: 2, name: 'Dye Liquor Pump (Sirkulasi Pompa Utama %)' },
  { id: 712, col: 3, name: 'Material Flow / Winch Speed (Kecepatan Kain m/min)' },
  { id: 717, col: 4, name: 'Filling AT1 Level (Pengisian Tangki Obat AT1)' },
  { id: 718, col: 5, name: 'Filling AT2 Level (Pengisian Tangki Obat AT2)' },
  { id: 720, col: 6, name: 'Fill Level ST (Pengisian Tangki Servis ST)' },
  { id: 237, col: 7, name: 'Inject AT1 (Injeksi Tangki Obat AT1 ke Mesin)' },
  { id: 238, col: 8, name: 'Inject AT2 (Injeksi Tangki Obat AT2 ke Mesin)' }
];

export default function Programs() {
  // Navigation / View State
  const [viewMode, setViewMode] = useState('LIST'); // 'LIST' or 'EDITOR'

  // Program List State
  const [programList, setProgramList] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL');

  // Editor State (Linear Step Studio)
  const [programNo, setProgramNo] = useState(182);
  const [programName, setProgramName] = useState('POLYESTER BLACK');
  const [machineCode, setMachineCode] = useState('C012');
  const [steps, setSteps] = useState([]);
  const [selectedStepIdx, setSelectedStepIdx] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [showChart, setShowChart] = useState(true);

  // Template Modal State
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [catalogTemplates, setCatalogTemplates] = useState([]);

  // Notifications
  const [notification, setNotification] = useState(null);

  // 1. Fetch Program List
  const fetchProgramList = async () => {
    setLoadingList(true);
    try {
      const res = await axios.get('/api/programs/');
      setProgramList(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil daftar program:', err);
    } finally {
      setLoadingList(false);
    }
  };

  // 2. Fetch Catalog Templates
  const fetchCatalogTemplates = async () => {
    try {
      const res = await axios.get('/api/programs/catalog-templates');
      setCatalogTemplates(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil template katalog:', err);
    }
  };

  useEffect(() => {
    fetchProgramList();
    fetchCatalogTemplates();
  }, []);

  // Filtered Programs
  const filteredPrograms = useMemo(() => {
    return programList.filter((prg) => {
      const pNoStr = String(prg.program_number || '');
      const pName = (prg.program_name || '').toLowerCase();
      const pFile = (prg.filename || '').toLowerCase();
      const term = searchTerm.toLowerCase();
      const matchSearch = pNoStr.includes(term) || pName.includes(term) || pFile.includes(term);

      if (filterType === 'CUSTOM') return matchSearch && prg.is_custom;
      if (filterType === 'MACHINE') return matchSearch && !prg.is_custom;
      return matchSearch;
    });
  }, [programList, searchTerm, filterType]);

  // Open Editor for an Existing Program
  const openEditorForProgram = async (pNo) => {
    try {
      const res = await axios.get(`/api/programs/${pNo}`);
      const data = res.data;
      setProgramNo(data.program_no || pNo);
      setProgramName(data.program_name || `M_${String(pNo).padStart(4, '0')}`);
      setMachineCode(data.machine_code || 'C012');

      const rawSteps = data.steps || [];
      if (rawSteps.length === 0) {
        // Build basic Start -> End template
        setSteps([
          { step_no: 1, label: 'Program Start', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] },
          { step_no: 2, label: 'Program End', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] }
        ]);
      } else {
        setSteps(rawSteps);
      }

      setSelectedStepIdx(0);
      setViewMode('EDITOR');
    } catch (err) {
      setNotification({
        type: 'error',
        title: 'Gagal Membuka Program',
        message: err.response?.data?.detail || err.message
      });
      setTimeout(() => setNotification(null), 4000);
    }
  };

  // Open Editor for New Program
  const openEditorForNewProgram = () => {
    const existingNos = programList.map(p => p.program_number).filter(n => Number.isInteger(n));
    const nextNo = existingNos.length > 0 ? Math.max(...existingNos) + 1 : 1;
    setProgramNo(nextNo);
    setProgramName('PROGRAM RESEP BARU');
    setMachineCode('C012');
    setSteps([
      { step_no: 1, label: 'Mulai Siklus Mesin', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] },
      { step_no: 2, label: 'Pengisian Air Awal', functions: [{ function_id: 713, column: 1, flags: 0, params: [1.0, 1800.0, 0, 0, 0, 0] }] },
      { step_no: 3, label: 'Penaikan Suhu', functions: [{ function_id: 141, column: 1, flags: 0, params: [98.0, 2.5, 30.0, 0, 0, 0] }] },
      { step_no: 4, label: 'Selesai Siklus', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] }
    ]);
    setSelectedStepIdx(1);
    setViewMode('EDITOR');
  };

  // Save Program
  const handleSaveProgram = async () => {
    setIsSaving(true);
    try {
      const payload = {
        program_no: parseInt(programNo),
        program_name: programName.trim().toUpperCase(),
        machine_code: machineCode,
        steps: steps
      };
      const res = await axios.post('/api/programs/', payload);
      setNotification({
        type: 'success',
        title: 'Program Berhasil Disimpan!',
        message: res.data.message || `Program M_${String(programNo).padStart(4, '0')}.PRG tersimpan di database.`
      });
      fetchProgramList();
    } catch (err) {
      setNotification({
        type: 'error',
        title: 'Gagal Menyimpan Program',
        message: err.response?.data?.detail || err.message
      });
    } finally {
      setIsSaving(false);
      setTimeout(() => setNotification(null), 4000);
    }
  };

  // Compile Binary
  const handleCompileBinary = async () => {
    try {
      const res = await axios.post(`/api/programs/compile/${programNo}`);
      setNotification({
        type: 'success',
        title: 'Kompilasi Biner Berhasil (Paritas SETEX 777)!',
        message: `${res.data.message} Ukuran: ${res.data.header?.binary_bytes} bytes.`
      });
    } catch (err) {
      setNotification({
        type: 'error',
        title: 'Kompilasi Gagal',
        message: err.response?.data?.detail || err.message
      });
    } finally {
      setTimeout(() => setNotification(null), 5000);
    }
  };

  // Download .PRG
  const handleDownloadPrg = (pNo) => {
    window.open(`/api/programs/download/${pNo}`, '_blank');
  };

  // Upload .PRG directly
  const handleUploadPrg = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const base64Data = String(reader.result).split(',')[1];
        const res = await axios.post('/api/programs/upload-prg', {
          filename: file.name,
          base64: base64Data
        });
        setNotification({
          type: 'success',
          title: 'Impor Sukses!',
          message: res.data.message || `Berkas ${file.name} berhasil diimpor.`
        });
        fetchProgramList();
        if (res.data.program) {
          openEditorForProgram(res.data.program.program_no);
        }
      } catch (err) {
        setNotification({
          type: 'error',
          title: 'Gagal Impor PRG',
          message: err.response?.data?.detail || err.message
        });
      } finally {
        e.target.value = '';
        setTimeout(() => setNotification(null), 5000);
      }
    };
    reader.readAsDataURL(file);
  };

  // Apply Reverse-Engineered Template
  const handleApplyTemplate = async (tmpl) => {
    setShowTemplateModal(false);
    openEditorForProgram(tmpl.id);
    setNotification({
      type: 'success',
      title: 'Template Berhasil Dimuat!',
      message: `Template "${tmpl.title}" dimuat ke editor (Program #${tmpl.id}).`
    });
    setTimeout(() => setNotification(null), 4000);
  };

  // STEP OPERATIONS
  const currentStep = steps[selectedStepIdx] || null;
  const isBoundaryStep = selectedStepIdx === 0 || selectedStepIdx === steps.length - 1;

  // Add Step before End
  const handleAddStep = () => {
    const insertIdx = Math.max(1, steps.length - 1);
    const newStepObj = {
      step_no: insertIdx + 1,
      label: 'Langkah Proses Baru',
      functions: [
        { function_id: 141, column: 1, flags: 0, params: [60.0, 2.0, 20.0, 0, 0, 0] }
      ]
    };
    const updated = [...steps];
    updated.splice(insertIdx, 0, newStepObj);
    // Renumber
    updated.forEach((s, idx) => { s.step_no = idx + 1; });
    setSteps(updated);
    setSelectedStepIdx(insertIdx);
  };

  // Duplicate Step
  const handleDuplicateStep = () => {
    if (isBoundaryStep) return;
    const cloned = JSON.parse(JSON.stringify(currentStep));
    const insertIdx = selectedStepIdx + 1;
    const updated = [...steps];
    updated.splice(insertIdx, 0, cloned);
    updated.forEach((s, idx) => { s.step_no = idx + 1; });
    setSteps(updated);
    setSelectedStepIdx(insertIdx);
  };

  // Move Step Up
  const handleMoveUp = () => {
    if (selectedStepIdx <= 1 || isBoundaryStep) return;
    const updated = [...steps];
    const prev = updated[selectedStepIdx - 1];
    updated[selectedStepIdx - 1] = updated[selectedStepIdx];
    updated[selectedStepIdx] = prev;
    updated.forEach((s, idx) => { s.step_no = idx + 1; });
    setSteps(updated);
    setSelectedStepIdx(selectedStepIdx - 1);
  };

  // Move Step Down
  const handleMoveDown = () => {
    if (selectedStepIdx >= steps.length - 2 || isBoundaryStep) return;
    const updated = [...steps];
    const nxt = updated[selectedStepIdx + 1];
    updated[selectedStepIdx + 1] = updated[selectedStepIdx];
    updated[selectedStepIdx] = nxt;
    updated.forEach((s, idx) => { s.step_no = idx + 1; });
    setSteps(updated);
    setSelectedStepIdx(selectedStepIdx + 1);
  };

  // Delete Step
  const handleDeleteStep = () => {
    if (isBoundaryStep) return;
    if (steps.length <= 2) {
      alert('Program harus memiliki minimal satu langkah antara Start dan End.');
      return;
    }
    const updated = steps.filter((_, idx) => idx !== selectedStepIdx);
    updated.forEach((s, idx) => { s.step_no = idx + 1; });
    setSteps(updated);
    setSelectedStepIdx(Math.min(selectedStepIdx, updated.length - 2));
  };

  // Update Current Step Label / Comment
  const handleUpdateLabel = (val) => {
    const updated = [...steps];
    updated[selectedStepIdx].label = val.slice(0, 61);
    setSteps(updated);
  };

  // Change Main Function (Column = 1)
  const handleChangeMainFunction = (newFuncId) => {
    const updated = [...steps];
    const step = updated[selectedStepIdx];
    const fDef = ALL_FUNCTIONS[String(newFuncId)];
    const defParams = [0, 0, 0, 0, 0, 0];
    if (fDef?.parameters) {
      fDef.parameters.forEach((p, i) => {
        if (i < 6) defParams[i] = p.default || 0;
      });
    }

    const mainFnIdx = step.functions.findIndex(f => f.column === 1);
    if (mainFnIdx >= 0) {
      step.functions[mainFnIdx].function_id = Number(newFuncId);
      step.functions[mainFnIdx].params = defParams;
    } else {
      step.functions.unshift({ function_id: Number(newFuncId), column: 1, flags: 0, params: defParams });
    }
    setSteps(updated);
  };

  // Update Parameter Value
  const handleUpdateParam = (fnIdx, pIdx, val) => {
    const updated = [...steps];
    const step = updated[selectedStepIdx];
    if (!step.functions[fnIdx].params) step.functions[fnIdx].params = [0, 0, 0, 0, 0, 0];
    step.functions[fnIdx].params[pIdx] = parseFloat(val) || 0;
    setSteps(updated);
  };

  // Add Parallel Function (Column 2..13)
  const handleAddParallelFunction = (funcId, col) => {
    const updated = [...steps];
    const step = updated[selectedStepIdx];
    const exists = step.functions.some(f => f.column === col);
    if (exists) {
      alert(`Resource slot ${col} sudah digunakan pada langkah ini.`);
      return;
    }
    const fDef = ALL_FUNCTIONS[String(funcId)];
    const defParams = [0, 0, 0, 0, 0, 0];
    if (fDef?.parameters) {
      fDef.parameters.forEach((p, i) => {
        if (i < 6) defParams[i] = p.default || 0;
      });
    }
    step.functions.push({
      function_id: Number(funcId),
      column: col,
      flags: 0,
      params: defParams
    });
    setSteps(updated);
  };

  // Remove Parallel Function
  const handleRemoveParallelFunction = (fnIdx) => {
    const updated = [...steps];
    updated[selectedStepIdx].functions.splice(fnIdx, 1);
    setSteps(updated);
  };

  // Compute Process Stats & Chart Series
  const { chartSeries, chartCategories, totalTimeMin, maxTemp, totalWaterL } = useMemo(() => {
    let tempSeries = [];
    let cats = [];
    let timeAcc = 0;
    let peakTemp = 25;
    let waterAcc = 0;

    steps.forEach((s, idx) => {
      const mainFn = s.functions.find(f => f.column === 1);
      const fId = mainFn?.function_id;
      const params = mainFn?.params || [];

      let curTemp = peakTemp;
      if (fId === 141 && params.length >= 3) { // Temp Control
        const targetT = params[0] || 25;
        const dur = params[2] || 0;
        timeAcc += dur;
        curTemp = targetT;
        if (targetT > peakTemp) peakTemp = targetT;
      } else if (fId === 713 && params.length >= 2) { // Water Fill
        waterAcc += (params[1] || 0);
      } else if (fId === 144) {
        timeAcc += (params[0] || 0);
      }

      tempSeries.push(curTemp);
      cats.push(`S${idx + 1}: ${s.label || `Langkah ${idx + 1}`}`);
    });

    return {
      chartSeries: [{ name: 'Target Suhu (°C)', data: tempSeries }],
      chartCategories: cats,
      totalTimeMin: Math.round(timeAcc),
      maxTemp: peakTemp,
      totalWaterL: Math.round(waterAcc)
    };
  }, [steps]);

  // Validation Checks
  const validationIssues = useMemo(() => {
    const issues = [];
    if (steps.length < 2) {
      issues.push('Program harus memiliki minimal langkah Start dan End.');
    } else {
      if (steps[0]?.functions?.find(f => f.column === 1)?.function_id !== 1) {
        issues.push('Langkah 1 WAJIB berupa "Program Start (F1)".');
      }
      if (steps[steps.length - 1]?.functions?.find(f => f.column === 1)?.function_id !== 2) {
        issues.push('Langkah terakhir WAJIB berupa "Program End (F2)".');
      }
    }
    return issues;
  }, [steps]);

  // =========================================================================
  // RENDER VIEW 1: PROGRAM CATALOG (LIST VIEW)
  // =========================================================================
  if (viewMode === 'LIST') {
    return (
      <div className="space-y-6">
        {/* NOTIFICATION */}
        {notification && (
          <div className={`flex items-center justify-between p-4 rounded-md border shadow-sm ${
            notification.type === 'success' 
              ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500/30 text-emerald-800 dark:text-emerald-300' 
              : 'bg-rose-50 dark:bg-rose-950/40 border-rose-500/30 text-rose-800 dark:text-rose-300'
          }`}>
            <div className="flex items-center gap-3">
              {notification.type === 'success' ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertCircle className="h-5 w-5 text-rose-600" />}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider">{notification.title}</h4>
                <p className="text-xs mt-0.5">{notification.message}</p>
              </div>
            </div>
            <button onClick={() => setNotification(null)} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
          </div>
        )}

        {/* HEADER BAR */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white dark:bg-boxdark p-5 rounded-lg border border-stroke dark:border-strokedark shadow-sm">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-black dark:text-white flex items-center gap-2">
                <FileCode className="h-6 w-6 text-primary" />
                Daftar Program Resep Celup (SECOM 777 .PRG)
              </h2>
              <span className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/20 font-mono">
                SETEX Studio Parity
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Editor linier langkah demi langkah kontroler SECOM 777/SC777CE dengan ekspor biner byte-exact.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={fetchProgramList}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 rounded border border-stroke dark:border-strokedark text-black dark:text-white shadow-sm transition"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingList ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>

            <label className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-blue-50 dark:bg-blue-950/40 hover:bg-blue-100 border border-blue-500/30 text-blue-700 dark:text-blue-300 rounded shadow-sm cursor-pointer transition">
              <Upload className="h-3.5 w-3.5" />
              <span>Impor .PRG</span>
              <input type="file" accept=".PRG,.prg" className="hidden" onChange={handleUploadPrg} />
            </label>

            <button
              onClick={openEditorForNewProgram}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white bg-primary hover:bg-primary/90 rounded shadow transition active:scale-95"
            >
              <Plus className="h-4 w-4" />
              <span>+ Buat Program Baru</span>
            </button>
          </div>
        </div>

        {/* SEARCH & FILTERS */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white dark:bg-boxdark p-3.5 rounded-lg border border-stroke dark:border-strokedark shadow-sm">
          <div className="relative flex-1 w-full sm:w-auto">
            <Search className="h-4 w-4 text-gray-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Cari berdasarkan nomor program (contoh: 182), nama resep, atau nama file..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full text-xs rounded border border-stroke bg-transparent py-2.5 pl-9 pr-4 text-black dark:text-white outline-none focus:border-primary transition"
            />
          </div>

          <div className="flex items-center gap-1 bg-gray-100 dark:bg-meta-4 p-1 rounded border border-stroke dark:border-strokedark">
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'ALL' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
            >
              Semua ({programList.length})
            </button>
            <button
              onClick={() => setFilterType('MACHINE')}
              className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'MACHINE' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
            >
              Template Mesin
            </button>
            <button
              onClick={() => setFilterType('CUSTOM')}
              className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'CUSTOM' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
            >
              Resep Custom
            </button>
          </div>
        </div>

        {/* PROGRAM TABLE */}
        <div className="bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark overflow-hidden shadow-sm">
          <table className="w-full text-left text-xs text-gray-600 dark:text-gray-300">
            <thead className="bg-gray-50 dark:bg-meta-4 border-b border-stroke dark:border-strokedark text-black dark:text-white font-bold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4 w-24">Nomor</th>
                <th className="py-3 px-4">Nama Program / Resep</th>
                <th className="py-3 px-4 w-36">Nama Berkas</th>
                <th className="py-3 px-4 text-center w-28">Jumlah Langkah</th>
                <th className="py-3 px-4 text-center w-28">Ukuran Biner</th>
                <th className="py-3 px-4 text-right w-48">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke dark:divide-strokedark font-medium">
              {filteredPrograms.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-gray-400">
                    Tidak ada program yang sesuai dengan kriteria pencarian.
                  </td>
                </tr>
              ) : (
                filteredPrograms.map((prg) => (
                  <tr key={prg.program_number} className="hover:bg-gray-50 dark:hover:bg-meta-4/40 transition">
                    <td className="py-3 px-4 font-mono font-bold text-primary">
                      #{String(prg.program_number).padStart(4, '0')}
                    </td>
                    <td className="py-3 px-4 font-bold text-black dark:text-white">
                      {prg.program_name}
                    </td>
                    <td className="py-3 px-4 font-mono text-gray-500">
                      {prg.filename || `M_${String(prg.program_number).padStart(4, '0')}.PRG`}
                    </td>
                    <td className="py-3 px-4 text-center font-bold">
                      <span className="bg-gray-100 dark:bg-meta-4 px-2 py-0.5 rounded text-[11px]">
                        {prg.total_steps || '-'} Steps
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center font-mono text-gray-400 text-[11px]">
                      {prg.file_size ? `${prg.file_size.toLocaleString()} B` : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleDownloadPrg(prg.program_number)}
                          className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-meta-4 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 rounded border border-stroke dark:border-strokedark transition"
                          title="Unduh biner M_xxxx.PRG"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>.PRG</span>
                        </button>
                        <button
                          onClick={() => openEditorForProgram(prg.program_number)}
                          className="flex items-center gap-1 px-3 py-1 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded shadow-sm transition"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                          <span>Buka Editor</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // =========================================================================
  // RENDER VIEW 2: LINEAR STEP SEQUENCE EDITOR (PRG STUDIO)
  // =========================================================================
  const mainFn = currentStep?.functions?.find(f => f.column === 1);
  const mainFnMeta = mainFn ? getFunctionMeta(mainFn.function_id) : null;
  const fDef = mainFn ? ALL_FUNCTIONS[String(mainFn.function_id)] : null;
  const parallelFns = currentStep?.functions?.filter(f => f.column > 1) || [];

  return (
    <div className="space-y-5">
      {/* NOTIFICATION */}
      {notification && (
        <div className={`flex items-center justify-between p-4 rounded-md border shadow-sm ${
          notification.type === 'success' 
            ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500/30 text-emerald-800 dark:text-emerald-300' 
            : 'bg-rose-50 dark:bg-rose-950/40 border-rose-500/30 text-rose-800 dark:text-rose-300'
        }`}>
          <div className="flex items-center gap-3">
            {notification.type === 'success' ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertCircle className="h-5 w-5 text-rose-600" />}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider">{notification.title}</h4>
              <p className="text-xs mt-0.5">{notification.message}</p>
            </div>
          </div>
          <button onClick={() => setNotification(null)} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* TOP HEADER & TOOLBAR */}
      <div className="bg-white dark:bg-boxdark p-4 rounded-lg border border-stroke dark:border-strokedark shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setViewMode('LIST')}
            className="p-2 bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 rounded text-gray-700 dark:text-gray-200 transition"
            title="Kembali ke Daftar Program"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2">
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold font-mono px-2 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded">
                  ID: {programNo}
                </span>
                <input
                  type="text"
                  value={programName}
                  onChange={(e) => setProgramName(e.target.value.toUpperCase())}
                  className="text-base font-black text-black dark:text-white uppercase tracking-wider bg-transparent border-b border-dashed border-gray-400 focus:border-primary outline-none px-1"
                  placeholder="NAMA PROGRAM RESEP"
                  maxLength={20}
                />
              </div>
              <span className="text-[11px] text-gray-400 font-mono mt-0.5">
                Target: M_{String(programNo).padStart(4, '0')}.PRG · {steps.length} Langkah
              </span>
            </div>
          </div>
        </div>

        {/* ACTIONS */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowTemplateModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-500/30 rounded shadow-sm hover:bg-amber-100 transition"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            <span>Pilih Template Mesin</span>
          </button>

          <button
            onClick={handleSaveProgram}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-sm transition"
          >
            <Save className={`h-3.5 w-3.5 ${isSaving ? 'animate-spin' : ''}`} />
            <span>{isSaving ? 'Menyimpan...' : 'Simpan Resep'}</span>
          </button>

          <button
            onClick={handleCompileBinary}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-white bg-meta-5 hover:bg-meta-5/90 rounded shadow-sm transition"
          >
            <FileCode className="h-3.5 w-3.5" />
            <span>Kompilasi Biner</span>
          </button>

          <button
            onClick={() => handleDownloadPrg(programNo)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded shadow-sm transition"
            title="Unduh file biner M_xxxx.PRG untuk mesin atau USB"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Unduh .PRG</span>
          </button>
        </div>
      </div>

      {/* PROCESS SUMMARY & CURVE ACCORDION */}
      <div className="bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-sm overflow-hidden">
        <div 
          onClick={() => setShowChart(!showChart)}
          className="px-4 py-3 bg-gray-50/80 dark:bg-meta-4/30 border-b border-stroke dark:border-strokedark flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-6">
            <span className="text-xs font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
              <Flame className="h-4 w-4 text-rose-500" />
              Profil Kurva Suhu & Ringkasan Proses
            </span>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="text-gray-500">Estimasi Waktu: <strong className="text-black dark:text-white">{totalTimeMin} min</strong></span>
              <span className="text-gray-500">Suhu Puncak: <strong className="text-rose-600">{maxTemp} °C</strong></span>
              <span className="text-gray-500">Total Air: <strong className="text-blue-600">{totalWaterL} L</strong></span>
            </div>
          </div>
          <button className="text-gray-400 hover:text-gray-600">
            {showChart ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {showChart && (
          <div className="p-4 border-b border-stroke dark:border-strokedark">
            <TempCurveChart series={chartSeries} categories={chartCategories} />
          </div>
        )}
      </div>

      {/* MAIN TWO-COLUMN STEP STUDIO */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        
        {/* KOLOM KIRI: DAFTAR LANGKAH LINEAR (5 COLS) */}
        <div className="lg:col-span-5 bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-sm overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 dark:bg-meta-4/30 border-b border-stroke dark:border-strokedark flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
              <Boxes className="h-4 w-4 text-primary" />
              Urutan Langkah ({steps.length})
            </span>
            <button
              onClick={handleAddStep}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold bg-primary hover:bg-primary/90 text-white rounded shadow-sm transition"
            >
              <Plus className="h-3 w-3" />
              <span>Tambah Langkah</span>
            </button>
          </div>

          <div className="divide-y divide-stroke dark:divide-strokedark max-h-[600px] overflow-y-auto">
            {steps.map((s, idx) => {
              const mFn = s.functions?.find(f => f.column === 1);
              const meta = mFn ? getFunctionMeta(mFn.function_id) : null;
              const isSelected = selectedStepIdx === idx;
              const isStart = idx === 0;
              const isEnd = idx === steps.length - 1;
              const params = mFn?.params || [];

              let badgeText = '';
              if (mFn?.function_id === 141) badgeText = `${params[0] || 0} °C · ${params[2] || 0} min`;
              else if (mFn?.function_id === 713) badgeText = `${params[1] || 0} L`;
              else if (mFn?.function_id === 71) badgeText = `Drain ${params[0] || 0}%`;

              return (
                <div
                  key={idx}
                  onClick={() => setSelectedStepIdx(idx)}
                  className={`p-3 cursor-pointer transition flex items-center justify-between ${
                    isSelected 
                      ? 'bg-primary/10 border-l-4 border-primary' 
                      : 'hover:bg-gray-50 dark:hover:bg-meta-4/30'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded flex items-center justify-center font-mono text-xs font-bold ${
                      isStart || isEnd ? 'bg-gray-200 dark:bg-meta-4 text-gray-700 dark:text-gray-300' : 'bg-primary text-white'
                    }`}>
                      {String(idx + 1).padStart(2, '0')}
                    </span>

                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-black dark:text-white">
                          {meta?.name || `Langkah ${idx + 1}`}
                        </span>
                        {badgeText && (
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 rounded border border-blue-500/20">
                            {badgeText}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-gray-400 truncate max-w-[200px]">
                        {s.label || 'Tanpa komentar'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <ChevronRight className={`h-4 w-4 ${isSelected ? 'text-primary' : 'text-gray-300'}`} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* KOLOM KANAN: DETAIL & PARAMETER LANGKAH AKTIF (7 COLS) */}
        <div className="lg:col-span-7 bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-sm p-5 space-y-5">
          {currentStep ? (
            <>
              {/* STEP ACTION TOOLBAR */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-stroke dark:border-strokedark gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-black text-primary px-2 py-0.5 bg-primary/10 rounded">
                      LANGKAH #{String(selectedStepIdx + 1).padStart(2, '0')}
                    </span>
                    <h3 className="text-base font-bold text-black dark:text-white">
                      {mainFnMeta?.name || 'Detail Langkah'}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={handleMoveUp}
                    disabled={selectedStepIdx <= 1 || isBoundaryStep}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 disabled:opacity-40 rounded border border-stroke dark:border-strokedark transition"
                    title="Geser Langkah Naik"
                  >
                    <ArrowUp className="h-3 w-3" />
                    <span>Naik</span>
                  </button>

                  <button
                    onClick={handleMoveDown}
                    disabled={selectedStepIdx >= steps.length - 2 || isBoundaryStep}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 disabled:opacity-40 rounded border border-stroke dark:border-strokedark transition"
                    title="Geser Langkah Turun"
                  >
                    <ArrowDown className="h-3 w-3" />
                    <span>Turun</span>
                  </button>

                  <button
                    onClick={handleDuplicateStep}
                    disabled={isBoundaryStep}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 disabled:opacity-40 rounded border border-stroke dark:border-strokedark transition"
                    title="Duplikasi Langkah"
                  >
                    <Copy className="h-3 w-3" />
                    <span>Duplikasi</span>
                  </button>

                  <button
                    onClick={handleDeleteStep}
                    disabled={isBoundaryStep}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-rose-50 text-rose-600 hover:bg-rose-100 disabled:opacity-40 rounded border border-rose-200 dark:bg-rose-950/40 dark:border-rose-900/50 transition"
                    title="Hapus Langkah"
                  >
                    <Trash2 className="h-3 w-3" />
                    <span>Hapus</span>
                  </button>
                </div>
              </div>

              {/* STEP COMMENT / LABEL */}
              <div>
                <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-1">
                  Komentar / Teks Tampilan Operator (Maksimal 61 Karakter)
                </label>
                <input
                  type="text"
                  value={currentStep.label || ''}
                  onChange={(e) => handleUpdateLabel(e.target.value)}
                  placeholder="Contoh: MASUK AIR DINGIN, PENAIKAN SUHU, SAMPEL WARNA"
                  maxLength={61}
                  className="w-full text-xs font-medium rounded border border-stroke bg-transparent py-2 px-3 text-black dark:text-white outline-none focus:border-primary transition"
                />
                <span className="text-[10px] text-gray-400 mt-0.5 block">
                  Teks ini akan muncul langsung pada baris status HMI SECOM saat langkah proses berjalan.
                </span>
              </div>

              {/* FUNGSI UTAMA (SLOT 1) */}
              <div className="bg-gray-50/80 dark:bg-meta-4/30 p-4 rounded-lg border border-stroke dark:border-strokedark space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
                    <Sliders className="h-3.5 w-3.5 text-primary" />
                    Fungsi Utama (Slot 1)
                  </span>
                  {isBoundaryStep && (
                    <span className="text-[10px] bg-amber-50 text-amber-700 font-bold px-2 py-0.5 rounded border border-amber-500/20">
                      Terkunci (Batas Siklus SECOM)
                    </span>
                  )}
                </div>

                {!isBoundaryStep && (
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-500 mb-1">Pilih Fungsi Utama:</label>
                    <select
                      value={mainFn?.function_id || 141}
                      onChange={(e) => handleChangeMainFunction(e.target.value)}
                      className="w-full text-xs font-bold rounded border border-stroke bg-white dark:bg-boxdark py-2 px-3 text-black dark:text-white outline-none focus:border-primary transition"
                    >
                      {POPULAR_MAIN_FUNCTIONS.map(pf => (
                        <option key={pf.id} value={pf.id}>F{pf.id} - {pf.name}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* PARAMETER FIELDS P1..P6 */}
                {fDef && fDef.parameters && fDef.parameters.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
                    {fDef.parameters.slice(0, 6).map((pMeta, pIdx) => {
                      const paramDef = ALL_PARAMETERS[String(pMeta.definition_id)];
                      const pName = paramDef?.name || `Parameter ${pIdx + 1}`;
                      const pUnit = paramDef?.unit || '';
                      const curVal = mainFn?.params?.[pIdx] ?? 0;

                      return (
                        <div key={pIdx} className="bg-white dark:bg-boxdark p-3 rounded border border-stroke dark:border-strokedark shadow-sm">
                          <label className="block text-[11px] font-bold text-gray-700 dark:text-gray-300 truncate" title={pName}>
                            P{pIdx + 1}: {pName}
                          </label>
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <input
                              type="number"
                              step="any"
                              value={curVal}
                              onChange={(e) => handleUpdateParam(0, pIdx, e.target.value)}
                              className="w-full text-xs font-mono font-bold rounded border border-stroke bg-transparent py-1.5 px-2 text-black dark:text-white outline-none focus:border-primary transition"
                            />
                            {pUnit && (
                              <span className="text-[11px] font-bold text-gray-500 font-mono bg-gray-100 dark:bg-meta-4 px-1.5 py-1 rounded">
                                {pUnit}
                              </span>
                            )}
                          </div>
                          <span className="text-[9px] text-gray-400 block mt-1">
                            Min: {pMeta.minimum} · Maks: {Math.round(pMeta.maximum)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-xs text-gray-400 italic py-2">
                    Fungsi ini tidak memerlukan parameter input numerik (F1 Start / F2 End).
                  </div>
                )}
              </div>

              {/* FUNGSI PARALEL / SUB-FUNGSI (SLOT 2..13) */}
              {!isBoundaryStep && (
                <div className="bg-gray-50/80 dark:bg-meta-4/30 p-4 rounded-lg border border-stroke dark:border-strokedark space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
                        <Gauge className="h-3.5 w-3.5 text-amber-500" />
                        Fungsi Paralel / Resource Tambahan (Slot 2–13)
                      </span>
                      <p className="text-[10px] text-gray-400">
                        Menjalankan pompa, winch, atau tangki dosing secara bersamaan di langkah yang sama.
                      </p>
                    </div>

                    {/* ADD PARALLEL DROPDOWN */}
                    <div className="flex items-center gap-2">
                      <select
                        id="parallel-selector"
                        className="text-xs rounded border border-stroke bg-white dark:bg-boxdark py-1 px-2 text-black dark:text-white outline-none"
                      >
                        {POPULAR_PARALLEL_FUNCTIONS.map(pf => (
                          <option key={pf.id} value={`${pf.id},${pf.col}`}>
                            Slot {pf.col}: {pf.name}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => {
                          const val = document.getElementById('parallel-selector').value;
                          const [fId, col] = val.split(',').map(Number);
                          handleAddParallelFunction(fId, col);
                        }}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white rounded shadow-sm transition"
                      >
                        <Plus className="h-3 w-3" />
                        <span>Tambah</span>
                      </button>
                    </div>
                  </div>

                  {parallelFns.length === 0 ? (
                    <div className="text-xs text-gray-400 italic py-2">
                      Belum ada fungsi paralel tambahan di langkah ini (hanya menjalankan fungsi utama).
                    </div>
                  ) : (
                    <div className="space-y-2 pt-1">
                      {parallelFns.map((fn, pFnIdx) => {
                        const actualIdx = currentStep.functions.findIndex(f => f.column === fn.column);
                        const fMeta = getFunctionMeta(fn.function_id);
                        const subDef = ALL_FUNCTIONS[String(fn.function_id)];

                        return (
                          <div key={fn.column} className="bg-white dark:bg-boxdark p-3 rounded border border-stroke dark:border-strokedark shadow-sm">
                            <div className="flex items-center justify-between pb-2 border-b border-stroke dark:border-strokedark">
                              <span className="text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1">
                                Slot {fn.column}: {fMeta.name}
                              </span>
                              <button
                                onClick={() => handleRemoveParallelFunction(actualIdx)}
                                className="text-rose-500 hover:text-rose-700 text-xs font-semibold"
                              >
                                Hapus
                              </button>
                            </div>

                            {subDef?.parameters && subDef.parameters.length > 0 && (
                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2">
                                {subDef.parameters.slice(0, 4).map((pMeta, pIdx) => {
                                  const paramDef = ALL_PARAMETERS[String(pMeta.definition_id)];
                                  const pName = paramDef?.name || `P${pIdx + 1}`;
                                  const pUnit = paramDef?.unit || '';
                                  const curVal = fn.params?.[pIdx] ?? 0;

                                  return (
                                    <div key={pIdx}>
                                      <label className="block text-[10px] font-bold text-gray-500 truncate">{pName}</label>
                                      <div className="flex items-center gap-1 mt-1">
                                        <input
                                          type="number"
                                          step="any"
                                          value={curVal}
                                          onChange={(e) => handleUpdateParam(actualIdx, pIdx, e.target.value)}
                                          className="w-full text-xs font-mono font-bold rounded border border-stroke bg-transparent py-1 px-1.5 text-black dark:text-white outline-none focus:border-primary"
                                        />
                                        {pUnit && <span className="text-[10px] text-gray-400 font-mono">{pUnit}</span>}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* VALIDATION BOX */}
              <div className={`p-3.5 rounded-lg border text-xs ${
                validationIssues.length === 0 
                  ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-500/30 text-emerald-800 dark:text-emerald-300' 
                  : 'bg-amber-50 dark:bg-amber-950/30 border-amber-500/30 text-amber-800 dark:text-amber-300'
              }`}>
                <div className="flex items-center gap-2 font-bold mb-1">
                  {validationIssues.length === 0 ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-amber-600" />}
                  <span>{validationIssues.length === 0 ? '✓ Struktur Program Valid (SETEX Secom 777 Ready)' : 'Perhatian Validasi SECOM:'}</span>
                </div>
                {validationIssues.length === 0 ? (
                  <p className="text-[11px]">
                    Langkah dimulai dari Program Start (F1) dan diakhiri Program End (F2). Siap dikompilasi atau diunduh ke HMI.
                  </p>
                ) : (
                  <ul className="list-disc list-inside text-[11px] space-y-0.5">
                    {validationIssues.map((iss, i) => <li key={i}>{iss}</li>)}
                  </ul>
                )}
              </div>
            </>
          ) : (
            <div className="py-12 text-center text-gray-400">
              Pilih langkah di sebelah kiri untuk mengedit parameter.
            </div>
          )}
        </div>
      </div>

      {/* TEMPLATE PICKER MODAL */}
      {showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-xl max-w-2xl w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-amber-500" />
                Pilih Template Program Mesin Asli
              </h3>
              <button onClick={() => setShowTemplateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-gray-500">
              Memuat template program asli SECOM 777 hasil ekstraksi mesin kontroler. Parameter langkah akan otomatis disesuaikan.
            </p>

            <div className="max-h-80 overflow-y-auto divide-y divide-stroke dark:divide-strokedark border rounded border-stroke dark:border-strokedark">
              {catalogTemplates.length === 0 ? (
                <div className="p-4 text-xs text-gray-400 text-center">Memuat daftar template...</div>
              ) : (
                catalogTemplates.map(tmpl => (
                  <div
                    key={tmpl.id}
                    onClick={() => handleApplyTemplate(tmpl)}
                    className="p-3 hover:bg-gray-50 dark:hover:bg-meta-4/40 cursor-pointer flex items-center justify-between transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-primary">#{tmpl.id}</span>
                        <strong className="text-xs text-black dark:text-white">{tmpl.title}</strong>
                      </div>
                      <span className="text-[11px] text-gray-400 font-mono">{tmpl.filename}</span>
                    </div>
                    <span className="text-xs bg-gray-100 dark:bg-meta-4 px-2 py-0.5 rounded font-mono font-bold">
                      {tmpl.steps} Langkah
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setShowTemplateModal(false)}
                className="px-4 py-2 text-xs font-semibold bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 rounded"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
