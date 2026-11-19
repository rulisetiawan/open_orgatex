import React, { useState, useEffect, useMemo, useRef } from 'react';
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
  ChevronUp,
  Cpu,
  Server,
  Send,
  Wand2,
  ListTree,
  List,
  Layers,
  BookOpen
} from 'lucide-react';

import TempCurveChart from '../components/Charts/TempCurveChart';
import ProcessPipelineBar from '../components/Programs/ProcessPipelineBar';
import SubProgramDrawer from '../components/Programs/SubProgramDrawer';
import SmartRecipeWizardModal from '../components/Programs/SmartRecipeWizardModal';
import typeconfData from '../data/typeconf_functions.json';

// Helper function definitions from TYPECONF
const ALL_FUNCTIONS = typeconfData.functions || {};
const ALL_PARAMETERS = typeconfData.parameters || {};

// Common function categories for colors
const getFunctionMeta = (funcId, funcsMap = ALL_FUNCTIONS) => {
  const f = (funcsMap && funcsMap[String(funcId)]) || ALL_FUNCTIONS[String(funcId)];
  const name = f?.name || f?.name_local || `Fungsi #${funcId}`;

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
  // Active Selected Machine (Synchronized across OrgaTEX & SETEX Studio)
  const [activeMachine, setActiveMachine] = useState(() => {
    return localStorage.getItem('selected_dyeing_machine') || 'TD12';
  });
  const [controllerModel, setControllerModel] = useState(() => {
    const savedM = localStorage.getItem('selected_dyeing_machine') || 'TD12';
    return localStorage.getItem('controller_model_' + savedM) || '777';
  });
  const [filterMachineScope, setFilterMachineScope] = useState('ACTIVE'); // 'ACTIVE' (Hanya Mesin Terpilih) | 'ALL' (Semua Mesin)

  // FTP Transfer Modal State
  const [ftpTransferModal, setFtpTransferModal] = useState(null); // { program_number, program_name, machine_code }
  const [isTransferringFtp, setIsTransferringFtp] = useState(false);

  // Machines List State
  const [machineList, setMachineList] = useState([]);

  // Create New Program Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createProgramNo, setCreateProgramNo] = useState(1);
  const [createProgramName, setCreateProgramName] = useState('PROGRAM RESEP BARU');
  const [createMachineCode, setCreateMachineCode] = useState(() => {
    return localStorage.getItem('selected_dyeing_machine') || 'TD12';
  });
  const [createTemplateType, setCreateTemplateType] = useState('STANDARD'); // 'STANDARD' | 'BLANK'

  // Editor State (Linear Step Studio & Hierarchical Sub-Program Model)
  const [programNo, setProgramNo] = useState(182);
  const [programName, setProgramName] = useState('POLYESTER BLACK');
  const [machineCode, setMachineCode] = useState(() => {
    return localStorage.getItem('selected_dyeing_machine') || 'TD12';
  });
  const [steps, setSteps] = useState([]);
  const [selectedStepIdx, setSelectedStepIdx] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [showChart, setShowChart] = useState(true);

  // Sub-Program & Fasa Architecture State
  const [subPrograms, setSubPrograms] = useState([]);
  const [isGroupedView, setIsGroupedView] = useState(true);
  const [expandedSubIds, setExpandedSubIds] = useState(new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]));
  const [showSubProgramDrawer, setShowSubProgramDrawer] = useState(false);
  const [showWizardModal, setShowWizardModal] = useState(false);
  const [activeSubIdx, setActiveSubIdx] = useState(0);

  // Intelligent Sub-Program / Fasa Partitioning
  const autoPartitionStepsToSubPrograms = (rawSteps) => {
    if (!rawSteps || rawSteps.length === 0) return [];

    const intermediate = rawSteps.filter((s, idx) => {
      if (idx === 0 && s.functions?.some(f => f.column === 1 && f.function_id === 1)) return false;
      if (idx === rawSteps.length - 1 && s.functions?.some(f => f.column === 1 && f.function_id === 2)) return false;
      return true;
    });

    if (intermediate.length === 0) {
      return [
        {
          id: 1,
          position: 1,
          treatment_number: 'TR-MAIN',
          treatment_name: 'Siklus Proses Utama',
          category: 'General',
          parameters: {},
          steps: []
        }
      ];
    }

    const groups = [];
    let curGroup = null;

    intermediate.forEach((step) => {
      const fId = step.functions?.find(f => f.column === 1)?.function_id || 0;
      const label = (step.label || '').toLowerCase();

      let cat = 'General';
      let phaseName = 'Modul Proses';
      let code = 'TR-MOD';

      if (fId === 713 || fId === 261 || label.includes('isi') || label.includes('muat') || label.includes('load') || label.includes('scour')) {
        cat = 'Pretreatment';
        phaseName = 'Prapengolahan / Persiapan';
        code = 'TR-PRE';
      } else if (fId === 141 || fId === 121 || fId === 85 || fId === 86 || fId === 938 || label.includes('celup') || label.includes('dye') || label.includes('suhu') || label.includes('reaktif') || label.includes('disperse')) {
        cat = 'Dyeing';
        phaseName = 'Pencelupan Utama';
        code = 'TR-DYE';
      } else if (fId === 127 || fId === 747 || label.includes('bilas') || label.includes('rinse')) {
        cat = 'Rinse';
        phaseName = 'Pembilasan';
        code = 'TR-RINSE';
      } else if (fId === 71 || fId === 122 || label.includes('drain') || label.includes('sabun') || label.includes('soap') || label.includes('cuci')) {
        cat = 'Washing';
        phaseName = 'Pencucian / Pembuangan';
        code = 'TR-WASH';
      }

      if (!curGroup || (curGroup.category !== cat && curGroup.steps.length >= 2)) {
        curGroup = {
          id: groups.length + 1,
          position: groups.length + 1,
          treatment_number: `${code}-${groups.length + 1}`,
          treatment_name: phaseName,
          category: cat,
          parameters: {},
          steps: [step]
        };
        groups.push(curGroup);
      } else {
        curGroup.steps.push(step);
        if (curGroup.category === 'General' && cat !== 'General') {
          curGroup.category = cat;
          curGroup.treatment_name = phaseName;
        }
      }
    });

    return groups.length > 0 ? groups : [
      {
        id: 1,
        position: 1,
        treatment_number: 'TR-MAIN',
        treatment_name: 'Siklus Proses Utama',
        category: 'General',
        parameters: {},
        steps: intermediate
      }
    ];
  };

  const flattenSubProgramsToSteps = (subProgs, existingSteps = []) => {
    const startStep = (existingSteps.length > 0 && existingSteps[0].functions?.some(f => f.column === 1 && f.function_id === 1))
      ? existingSteps[0]
      : { step_no: 1, label: 'Program Start (Mulai Siklus Mesin)', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] };

    const endStep = (existingSteps.length > 0 && existingSteps[existingSteps.length - 1].functions?.some(f => f.column === 1 && f.function_id === 2))
      ? existingSteps[existingSteps.length - 1]
      : { step_no: 99, label: 'Program End (Selesai Siklus)', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] };

    const flattened = [{ ...startStep, step_no: 1 }];
    let counter = 2;

    (subProgs || []).forEach(sub => {
      (sub.steps || []).forEach(st => {
        flattened.push({
          ...st,
          step_no: counter++
        });
      });
    });

    flattened.push({ ...endStep, step_no: counter });
    return flattened;
  };

  // Template Modal State
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [catalogTemplates, setCatalogTemplates] = useState([]);
  const [syncingDB, setSyncingDB] = useState(false);

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

  // 3. Fetch Registered Machines
  const fetchMachines = async () => {
    try {
      const res = await axios.get('/api/machines/');
      if (Array.isArray(res.data) && res.data.length > 0) {
        setMachineList(res.data);
      }
    } catch (err) {
      console.error('Gagal mengambil daftar mesin:', err);
    }
  };

  // 4. Sync PostgreSQL & SQLite Database
  const handleSyncDB = async () => {
    setSyncingDB(true);
    try {
      const res = await axios.post('/api/database/sync');
      alert(res.data.message || 'Sinkronisasi program PostgreSQL & SQLite selesai!');
      fetchProgramList();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      alert('Gagal sinkronisasi program: ' + msg);
    } finally {
      setSyncingDB(false);
    }
  };

  useEffect(() => {
    fetchProgramList();
    fetchCatalogTemplates();
    fetchMachines();
  }, []);

  // Machine-Specific Configuration State (from WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/02_CONFIG_SIAP_PAKAI/)
  const [machineFunctions, setMachineFunctions] = useState(ALL_FUNCTIONS);
  const [machineParameters, setMachineParameters] = useState(ALL_PARAMETERS);
  const [parallelOptions, setParallelOptions] = useState(POPULAR_PARALLEL_FUNCTIONS);

  // Fetch machine-specific workspace configuration (TYPECONF.CNF & CONFTEXT.CNF per machine)
  useEffect(() => {
    const fetchMachineConfig = async () => {
      try {
        const cleanNo = activeMachine.trim().toUpperCase().replace('MESIN_', '');
        const res = await axios.get(`/api/programs/machine-workspace/${cleanNo}/config`);
        if (res.data?.functions && Object.keys(res.data.functions).length > 0) {
          const funcs = res.data.functions;
          const params = res.data.parameters || ALL_PARAMETERS;
          setMachineFunctions(funcs);
          setMachineParameters(params);

          // Build dynamic parallel options based on this machine's actual downloaded functions!
          const dynamicOptions = [];

          // Slot 2: Pump (F404 / F401)
          const pumpFn = funcs['404'] || funcs['401'];
          if (pumpFn) {
            dynamicOptions.push({ id: pumpFn.id, col: 2, name: `${pumpFn.name} (${pumpFn.name_local || 'Sirkulasi Pompa'})` });
          } else {
            dynamicOptions.push({ id: 404, col: 2, name: 'Dye Liquor Pump (Sirkulasi Pompa Utama %)' });
          }

          // Slot 3: Winch / Material Flow (F712)
          const winchFn = funcs['712'];
          if (winchFn) {
            dynamicOptions.push({ id: winchFn.id, col: 3, name: `${winchFn.name} (${winchFn.name_local || 'Kecepatan Winch'})` });
          } else {
            dynamicOptions.push({ id: 712, col: 3, name: 'Material Flow / Winch Speed (Kecepatan Kain m/min)' });
          }

          // Slot 4: AT1 / Tangki 1 (F717 / F667)
          const at1Fill = funcs['717'] || funcs['667'];
          if (at1Fill) {
            dynamicOptions.push({ id: at1Fill.id, col: 4, name: `${at1Fill.name} (${at1Fill.name_local || 'Pengisian AT1'})` });
          } else {
            dynamicOptions.push({ id: 717, col: 4, name: 'Filling AT1 Level (Pengisian Tangki Obat AT1)' });
          }

          // Slot 5: AT2 / Tangki 2 (F718 / F668)
          const at2Fill = funcs['718'] || funcs['668'];
          if (at2Fill) {
            dynamicOptions.push({ id: at2Fill.id, col: 5, name: `${at2Fill.name} (${at2Fill.name_local || 'Pengisian AT2'})` });
          } else {
            dynamicOptions.push({ id: 718, col: 5, name: 'Filling AT2 Level (Pengisian Tangki Obat AT2)' });
          }

          // Slot 6: ST / Tangki Servis (F720 / F678)
          const stFill = funcs['720'] || funcs['678'];
          if (stFill) {
            dynamicOptions.push({ id: stFill.id, col: 6, name: `${stFill.name} (${stFill.name_local || 'Pengisian Tangki Servis'})` });
          } else {
            dynamicOptions.push({ id: 720, col: 6, name: 'Fill Level ST (Pengisian Tangki Servis ST)' });
          }

          // Slot 7: Inject AT1 (F237 / F661)
          const at1Inj = funcs['237'] || funcs['661'];
          if (at1Inj) {
            dynamicOptions.push({ id: at1Inj.id, col: 7, name: `${at1Inj.name} (${at1Inj.name_local || 'Injeksi AT1'})` });
          } else {
            dynamicOptions.push({ id: 237, col: 7, name: 'Inject AT1 (Injeksi Tangki Obat AT1 ke Mesin)' });
          }

          // Slot 8: Inject AT2 (F238 / F702)
          const at2Inj = funcs['238'] || funcs['702'];
          if (at2Inj) {
            dynamicOptions.push({ id: at2Inj.id, col: 8, name: `${at2Inj.name} (${at2Inj.name_local || 'Injeksi AT2'})` });
          } else {
            dynamicOptions.push({ id: 238, col: 8, name: 'Inject AT2 (Injeksi Tangki Obat AT2 ke Mesin)' });
          }

          setParallelOptions(dynamicOptions);
        } else {
          setMachineFunctions(ALL_FUNCTIONS);
          setMachineParameters(ALL_PARAMETERS);
          setParallelOptions(POPULAR_PARALLEL_FUNCTIONS);
        }
      } catch (err) {
        setMachineFunctions(ALL_FUNCTIONS);
        setMachineParameters(ALL_PARAMETERS);
        setParallelOptions(POPULAR_PARALLEL_FUNCTIONS);
      }
    };

    fetchMachineConfig();
  }, [activeMachine]);

  // Available Machines (with fallback to default factory controllers)
  const availableMachines = useMemo(() => {
    const defaults = [
      { machine_no: 'DA01', display_name: 'DA01 - SETEX 797CE Mesin DA01', ip_address: '192.168.1.95', ftp_port: 21, controller_type: '797' },
      { machine_no: '797', display_name: '797 - SETEX 797CE Controller', ip_address: '192.168.1.95', ftp_port: 21, controller_type: '797' },
      { machine_no: '10B', display_name: '10B - Mesin 10B (Novatech/SETEX)', ip_address: '172.16.110.160', ftp_port: 21, controller_type: '777' },
      { machine_no: 'TD12', display_name: 'TD12 - SETEX Controller', ip_address: '172.16.110.101', ftp_port: 21, controller_type: '777' },
      { machine_no: 'A002', display_name: 'A002 - Jet Dyeing Mesin 2', ip_address: '172.16.110.102', ftp_port: 21, controller_type: '777' },
      { machine_no: 'A003', display_name: 'A003 - Jet Dyeing Mesin 3', ip_address: '172.16.110.103', ftp_port: 21, controller_type: '777' },
      { machine_no: '1A', display_name: '1A - Jet Dyeing Mesin 1A', ip_address: '172.16.110.104', ftp_port: 21, controller_type: '777' },
    ];
    if (!machineList || machineList.length === 0) return defaults;
    const existingNos = new Set(machineList.map(m => m.machine_no));
    const merged = [...machineList];
    defaults.forEach(d => {
      if (!existingNos.has(d.machine_no)) merged.push(d);
    });
    return merged;
  }, [machineList]);

  // Active selected machine details
  const selectedMachineObj = useMemo(() => {
    return availableMachines.find(m => m.machine_no.toUpperCase() === activeMachine.toUpperCase()) || availableMachines[0];
  }, [availableMachines, activeMachine]);

  // Select Machine Handler (Persisted in localStorage)
  const handleSelectMachine = (code) => {
    const clean = code.trim().toUpperCase();
    setActiveMachine(clean);
    setMachineCode(clean);
    localStorage.setItem('selected_dyeing_machine', clean);

    const mObj = availableMachines.find(m => m.machine_no.toUpperCase() === clean);
    const is797Machine = (mObj?.ip_address === '192.168.1.95') || clean.includes('797') || clean.startsWith('DA');
    const savedModel = is797Machine ? '797' : (localStorage.getItem('controller_model_' + clean) || '777');
    setControllerModel(savedModel);
  };

  const handleSelectControllerModel = (model) => {
    setControllerModel(model);
    localStorage.setItem('controller_model_' + activeMachine, model);
  };

  const currentRemoteDir = controllerModel === '797'
    ? '/Flashdisk/SC797CE/Programs'
    : '/Storage/sc777ce/Programs';

  // Transfer Program to FTP Controller Handler
  const handleTransferToFtp = async (pNo, mCode, customDir) => {
    const num = parseInt(pNo, 10);
    if (isNaN(num) || num < 1 || num > 9999) {
      setNotification({
        type: 'error',
        title: 'Nomor Program Tidak Valid',
        message: `Nomor program (${pNo}) tidak valid. Harus antara 1 sampai 9999 (format M_xxxx.PRG).`
      });
      return;
    }
    const targetM = (mCode || activeMachine).trim().toUpperCase();
    const targetObj = availableMachines.find(m => m.machine_no.toUpperCase() === targetM) || selectedMachineObj;
    setIsTransferringFtp(true);
    try {
      const res = await axios.post(`/api/programs/transfer-ftp/${pNo}`, {
        machine_code: targetM,
        ip_address: targetObj?.ip_address,
        controller_type: controllerModel,
        target_dir: customDir || currentRemoteDir,
        timeout: 6.0
      });
      setNotification({
        type: 'success',
        title: 'Transfer FTP Berhasil!',
        message: res.data.message
      });
      setFtpTransferModal(null);
    } catch (err) {
      setNotification({
        type: 'error',
        title: 'Gagal Menulis ke FTP',
        message: err.response?.data?.detail || err.message
      });
    } finally {
      setIsTransferringFtp(false);
      setTimeout(() => setNotification(null), 6000);
    }
  };

  // State & Handlers for Downloading / Uploading Programs to Machine
  const [isFetchingFromMachine, setIsFetchingFromMachine] = useState(false);
  const fileInputRef = useRef(null);

  const handleFetchProgramsFromMachine = async () => {
    setIsFetchingFromMachine(true);
    try {
      const res = await axios.post(`/api/programs/fetch-from-machine/${activeMachine}`, {
        ip_address: selectedMachineObj?.ip_address,
        controller_type: controllerModel,
        remote_dir: currentRemoteDir,
        timeout: 10.0
      });
      setNotification({
        type: res.data.success ? 'success' : 'error',
        title: res.data.success ? 'Unduh Program Berhasil!' : 'Pemberitahuan Unduh Program',
        message: res.data.message || `Pemeriksaan program Mesin ${activeMachine} selesai.`
      });
      await fetchProgramList();
      setFilterMachineScope('ACTIVE');
    } catch (err) {
      setNotification({
        type: 'error',
        title: 'Gagal Mengunduh Program',
        message: err.response?.data?.detail || err.message
      });
    } finally {
      setIsFetchingFromMachine(false);
      setTimeout(() => setNotification(null), 6000);
    }
  };

  const handleUploadPrg = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const base64Content = reader.result.split(',')[1];
        const res = await axios.post(`/api/programs/upload-prg?machine_code=${activeMachine}`, {
          filename: file.name,
          base64: base64Content,
          machine_code: activeMachine
        });
        setNotification({
          type: 'success',
          title: 'Impor .PRG Berhasil!',
          message: res.data.message || `File ${file.name} berhasil diimpor untuk Mesin ${activeMachine}!`
        });
        await fetchProgramList();
        setFilterMachineScope('ACTIVE');
        if (res.data.program) {
          openEditorForProgram(res.data.program.program_no);
        }
      } catch (err) {
        setNotification({
          type: 'error',
          title: 'Gagal Mengimpor .PRG',
          message: err.response?.data?.detail || err.message
        });
      } finally {
        setTimeout(() => setNotification(null), 5000);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  // Count programs for active machine
  const activeMachineProgramsCount = useMemo(() => {
    return programList.filter(p => (p.machine_code || 'TD12').toUpperCase() === activeMachine.toUpperCase()).length;
  }, [programList, activeMachine]);

  // Filtered Programs
  const filteredPrograms = useMemo(() => {
    return programList.filter((prg) => {
      const pNoStr = String(prg.program_number || '');
      const pName = (prg.program_name || '').toLowerCase();
      const pFile = (prg.filename || '').toLowerCase();
      const pMach = (prg.machine_code || 'TD12').toUpperCase();
      const term = searchTerm.toLowerCase();
      const matchSearch = pNoStr.includes(term) || pName.includes(term) || pFile.includes(term) || pMach.toLowerCase().includes(term);

      if (filterMachineScope === 'ACTIVE' && pMach !== activeMachine.toUpperCase()) {
        return false;
      }
      if (filterType === 'CUSTOM') return matchSearch && prg.is_custom;
      if (filterType === 'MACHINE') return matchSearch && !prg.is_custom;
      return matchSearch;
    });
  }, [programList, searchTerm, filterType, filterMachineScope, activeMachine]);

  // Open Editor for an Existing Program
  const openEditorForProgram = async (pNo) => {
    try {
      const res = await axios.get(`/api/programs/${pNo}`);
      const data = res.data;
      setProgramNo(data.program_no || pNo);
      setProgramName(data.program_name || `M_${String(pNo).padStart(4, '0')}`);
      setMachineCode(data.machine_code || activeMachine);

      const rawSteps = data.steps || [];
      if (rawSteps.length === 0) {
        // Build basic Start -> End template
        const baseSteps = [
          { step_no: 1, label: 'Program Start', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] },
          { step_no: 2, label: 'Program End', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] }
        ];
        setSteps(baseSteps);
        setSubPrograms([]);
      } else {
        setSteps(rawSteps);
        if (data.sub_programs && data.sub_programs.length > 0) {
          setSubPrograms(data.sub_programs);
        } else {
          setSubPrograms(autoPartitionStepsToSubPrograms(rawSteps));
        }
      }

      setSelectedStepIdx(0);
      setActiveSubIdx(0);
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

  // Open Modal for New Program
  const handleOpenCreateModal = () => {
    const existingNos = programList
      .map(p => p.program_number)
      .filter(n => Number.isInteger(n) && n >= 1 && n <= 9999);
    const nextNo = existingNos.length > 0 ? Math.min(Math.max(...existingNos) + 1, 9999) : 1;
    setCreateProgramNo(nextNo);
    setCreateProgramName(`RESEP MESIN ${activeMachine}`);
    setCreateMachineCode(activeMachine);
    setCreateTemplateType('STANDARD');
    setShowCreateModal(true);
  };

  // Confirm and Create New Program
  const handleConfirmCreateProgram = () => {
    const pNo = parseInt(createProgramNo, 10);
    if (isNaN(pNo) || pNo < 1 || pNo > 9999) {
      alert("Nomor program harus antara 1 sampai 9999 (format SETEX M_xxxx.PRG).");
      return;
    }
    setProgramNo(pNo);
    setProgramName(createProgramName.trim().toUpperCase() || `PROGRAM #${pNo}`);
    setMachineCode(createMachineCode);

    if (createTemplateType === 'STANDARD') {
      const stdSteps = [
        { step_no: 1, label: 'Mulai Siklus Mesin', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] },
        { step_no: 2, label: 'Pengisian Air Awal', functions: [{ function_id: 713, column: 1, flags: 0, params: [1.0, 1800.0, 0, 0, 0, 0] }] },
        { step_no: 3, label: 'Penaikan Suhu', functions: [{ function_id: 141, column: 1, flags: 0, params: [98.0, 2.5, 30.0, 0, 0, 0] }] },
        { step_no: 4, label: 'Selesai Siklus', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] }
      ];
      setSteps(stdSteps);
      setSubPrograms(autoPartitionStepsToSubPrograms(stdSteps));
    } else {
      const blankSteps = [
        { step_no: 1, label: 'Program Start', functions: [{ function_id: 1, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] },
        { step_no: 2, label: 'Program End', functions: [{ function_id: 2, column: 1, flags: 0, params: [0, 0, 0, 0, 0, 0] }] }
      ];
      setSteps(blankSteps);
      setSubPrograms([]);
    }
    setSelectedStepIdx(1);
    setActiveSubIdx(0);
    setShowCreateModal(false);
    setViewMode('EDITOR');
  };

  // Save Program
  const handleSaveProgram = async () => {
    const pNo = parseInt(programNo, 10);
    if (isNaN(pNo) || pNo < 1 || pNo > 9999) {
      setNotification({
        type: 'error',
        title: 'Nomor Program Tidak Valid',
        message: 'Nomor program SETEX harus antara 1 sampai 9999 (format 4 digit M_xxxx.PRG).'
      });
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        program_no: pNo,
        program_name: programName.trim().toUpperCase(),
        machine_code: machineCode,
        sub_programs: subPrograms,
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

  // Sub-Program & Fasa Operations
  const handleMoveSubProgram = (subIdx, direction) => {
    if (direction === 'LEFT' || direction === 'UP') {
      if (subIdx <= 0) return;
      const updated = [...subPrograms];
      const temp = updated[subIdx - 1];
      updated[subIdx - 1] = updated[subIdx];
      updated[subIdx] = temp;
      updated.forEach((s, i) => { s.position = i + 1; });
      setSubPrograms(updated);
      const newSteps = flattenSubProgramsToSteps(updated, steps);
      setSteps(newSteps);
      setActiveSubIdx(subIdx - 1);
    } else {
      if (subIdx >= subPrograms.length - 1) return;
      const updated = [...subPrograms];
      const temp = updated[subIdx + 1];
      updated[subIdx + 1] = updated[subIdx];
      updated[subIdx] = temp;
      updated.forEach((s, i) => { s.position = i + 1; });
      setSubPrograms(updated);
      const newSteps = flattenSubProgramsToSteps(updated, steps);
      setSteps(newSteps);
      setActiveSubIdx(subIdx + 1);
    }
  };

  const handleDuplicateSubProgram = (subIdx) => {
    const target = subPrograms[subIdx];
    if (!target) return;
    const cloned = JSON.parse(JSON.stringify(target));
    cloned.id = Date.now();
    cloned.treatment_name = `${cloned.treatment_name || cloned.name} (Salinan)`;
    const updated = [...subPrograms];
    updated.splice(subIdx + 1, 0, cloned);
    updated.forEach((s, i) => { s.position = i + 1; });
    setSubPrograms(updated);
    const newSteps = flattenSubProgramsToSteps(updated, steps);
    setSteps(newSteps);
    setActiveSubIdx(subIdx + 1);
    setExpandedSubIds(prev => new Set([...prev, cloned.id]));
    setNotification({
      type: 'success',
      title: 'Sub-Program Diduplikasi',
      message: `Modul "${cloned.treatment_name}" berhasil digandakan ke dalam resep!`
    });
    setTimeout(() => setNotification(null), 3500);
  };

  const handleDeleteSubProgram = (subIdx) => {
    if (subPrograms.length <= 1) {
      alert("Resep harus memiliki minimal 1 sub-program / fasa proses.");
      return;
    }
    const removedName = subPrograms[subIdx]?.treatment_name || `Fasa #${subIdx + 1}`;
    const updated = subPrograms.filter((_, idx) => idx !== subIdx);
    updated.forEach((s, i) => { s.position = i + 1; });
    setSubPrograms(updated);
    const newSteps = flattenSubProgramsToSteps(updated, steps);
    setSteps(newSteps);
    setActiveSubIdx(Math.max(0, subIdx - 1));
    setNotification({
      type: 'success',
      title: 'Sub-Program Dihapus',
      message: `Modul "${removedName}" telah dihapus dari urutan proses.`
    });
    setTimeout(() => setNotification(null), 3500);
  };

  const handleInsertSubProgramFromDrawer = (treatment) => {
    const newSub = {
      id: Date.now(),
      position: subPrograms.length + 1,
      treatment_number: treatment.number,
      treatment_name: treatment.name,
      category: treatment.category || 'General',
      parameters: treatment.parameters || {},
      steps: treatment.steps || []
    };
    const updated = [...subPrograms, newSub];
    setSubPrograms(updated);
    const newSteps = flattenSubProgramsToSteps(updated, steps);
    setSteps(newSteps);
    setActiveSubIdx(updated.length - 1);
    setExpandedSubIds(prev => new Set([...prev, newSub.id]));
    setNotification({
      type: 'success',
      title: 'Fasa Berhasil Disisipkan!',
      message: `Modul "${treatment.name}" (${treatment.steps?.length || 0} langkah) ditambahkan ke program.`
    });
    setTimeout(() => setNotification(null), 4000);
  };

  const handleAddStepToSubProgram = (subIdx) => {
    const updatedSubs = [...subPrograms];
    const sub = updatedSubs[subIdx];
    if (!sub) return;

    const newMicroStep = {
      step_no: (sub.steps?.length || 0) + 1,
      label: `Langkah Baru (${sub.treatment_name || 'Fasa'})`,
      functions: [{ function_id: 141, column: 1, flags: 0, params: [60.0, 2.0, 15.0, 0, 0, 0] }]
    };

    if (!sub.steps) sub.steps = [];
    sub.steps.push(newMicroStep);

    setSubPrograms(updatedSubs);
    const newSteps = flattenSubProgramsToSteps(updatedSubs, steps);
    setSteps(newSteps);

    let globalIdx = 1;
    for (let i = 0; i <= subIdx; i++) {
      if (i < subIdx) {
        globalIdx += updatedSubs[i].steps?.length || 0;
      } else {
        globalIdx += updatedSubs[i].steps?.length - 1;
      }
    }
    setSelectedStepIdx(globalIdx);
  };

  const handleApplyWizardRecipe = (wizardData) => {
    setProgramNo(wizardData.program_no);
    setProgramName(wizardData.program_name);
    setMachineCode(wizardData.machine_code);
    setSubPrograms(wizardData.sub_programs || []);
    setSteps(wizardData.steps || []);
    setSelectedStepIdx(1);
    setActiveSubIdx(0);
    setNotification({
      type: 'success',
      title: 'Resep Otomatis Terbentuk!',
      message: `Program "${wizardData.program_name}" (${wizardData.sub_programs?.length || 0} Fasa, ${wizardData.steps?.length || 0} Langkah) siap digunakan!`
    });
    setTimeout(() => setNotification(null), 5000);
  };

  // Compile Binary
  const handleCompileBinary = async () => {
    const pNo = parseInt(programNo, 10);
    if (isNaN(pNo) || pNo < 1 || pNo > 9999) {
      setNotification({
        type: 'error',
        title: 'Nomor Program Tidak Valid',
        message: 'Nomor program SETEX harus antara 1 sampai 9999 (format 4 digit M_xxxx.PRG).'
      });
      return;
    }
    try {
      const res = await axios.post(`/api/programs/compile/${pNo}`);
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
    const fDef = (machineFunctions && machineFunctions[String(newFuncId)]) || ALL_FUNCTIONS[String(newFuncId)];
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
    const fDef = (machineFunctions && machineFunctions[String(funcId)]) || ALL_FUNCTIONS[String(funcId)];
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
          <div className={`flex items-center justify-between p-4 rounded-md border shadow-sm ${notification.type === 'success'
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
              Editor linier langkah demi langkah kontroler SECOM 777/sc777ce dengan ekspor biner byte-exact.
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
              onClick={handleOpenCreateModal}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white bg-primary hover:bg-primary/90 rounded shadow transition active:scale-95"
            >
              <Plus className="h-4 w-4" />
              <span>+ Buat Program Baru</span>
            </button>
          </div>
        </div>

        {/* BILAH PILIHAN MESIN AKTIF & STATUS KONTROLER FTP */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-4 sm:p-5 rounded-xl border border-indigo-500/30 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-3 bg-indigo-500/20 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Cpu className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                  Mesin Kontroler Aktif Terpilih:
                </span>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Siap FTP Port 21
                </span>
              </div>
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <span>Mesin {activeMachine}</span>
                <span className="text-xs font-normal text-indigo-200">
                  — {selectedMachineObj?.display_name || activeMachine}
                </span>
              </h3>
              <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-300 mt-1">
                <span>IP Host FTP: <strong className="text-emerald-400">{selectedMachineObj?.ip_address || '172.16.110.101'}:21</strong></span>
                <span>•</span>
                <span>Folder Remote: <strong className="text-indigo-300">{currentRemoteDir}</strong></span>
                <span>•</span>
                <span className="text-amber-300 font-semibold">Tipe: SECOM {controllerModel}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 bg-slate-800/80 p-2.5 rounded-xl border border-slate-700">
            <div className="flex flex-col">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Ganti Pilihan Mesin:
              </label>
              <select
                value={activeMachine}
                onChange={(e) => handleSelectMachine(e.target.value)}
                className="text-xs font-bold font-mono bg-slate-900 border border-indigo-500/50 rounded px-2.5 py-1.5 text-indigo-300 outline-none cursor-pointer hover:border-indigo-400 transition"
              >
                {availableMachines.map((m) => (
                  <option key={m.machine_no} value={m.machine_no} className="bg-boxdark text-white">
                    Mesin {m.machine_no} ({m.ip_address})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Model Kontroler / Folder:
              </label>
              <select
                value={controllerModel}
                onChange={(e) => handleSelectControllerModel(e.target.value)}
                className="text-xs font-bold font-mono bg-slate-900 border border-emerald-500/50 rounded px-2.5 py-1.5 text-emerald-300 outline-none cursor-pointer hover:border-emerald-400 transition"
                title="Pilih folder kontroler: SECOM 777 (/Storage/SC777CE) atau SECOM 797 (/Flashdisk/SC797CE)"
              >
                <option value="777" className="bg-boxdark text-white">
                  SETEX 777 (/Storage/SC777CE)
                </option>
                <option value="797" className="bg-boxdark text-white">
                  SETEX 797 (/Flashdisk/SC797CE)
                </option>
              </select>
            </div>

            <div className="flex items-center gap-2 pt-2 md:pt-0">
              <button
                onClick={handleFetchProgramsFromMachine}
                disabled={isFetchingFromMachine}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md transition disabled:opacity-50"
                title={`Unduh seluruh file .PRG dari kontroler Mesin ${activeMachine} (${selectedMachineObj?.ip_address || ''}) via FTP`}
              >
                {isFetchingFromMachine ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Mengunduh...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Unduh Program Mesin {activeMachine} (FTP)</span>
                  </>
                )}
              </button>

              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium border border-slate-600 transition"
                title={`Impor file biner .PRG dari Storage untuk Mesin ${activeMachine}`}
              >
                <Upload className="w-3.5 h-3.5 text-indigo-300" />
                <span>Impor .PRG</span>
              </button>
              <button
                onClick={handleSyncDB}
                disabled={syncingDB}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-900/40 hover:bg-blue-800/60 border border-blue-500/50 text-blue-300 text-xs font-semibold shadow-md transition disabled:opacity-50"
                title="Sinkronkan seluruh database program antara PostgreSQL pt_smm_jetflow dan SQLite lokal"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncingDB ? 'animate-spin text-blue-400' : 'text-blue-400'}`} />
                <span>{syncingDB ? 'Syncing...' : 'Sync DB'}</span>
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleUploadPrg}
                accept=".prg,.PRG"
                className="hidden"
              />
            </div>
          </div>
        </div>

        {/* SEARCH & FILTERS */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-3 bg-white dark:bg-boxdark p-3.5 rounded-lg border border-stroke dark:border-strokedark shadow-sm">
          <div className="relative flex-1 w-full">
            <Search className="h-4 w-4 text-gray-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder={`Cari program mesin ${activeMachine} (contoh: 182), nama resep, atau nama file...`}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full text-xs rounded border border-stroke bg-transparent py-2.5 pl-9 pr-4 text-black dark:text-white outline-none focus:border-primary transition"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            {/* Filter Lingkup Mesin */}
            <div className="flex items-center gap-1 bg-gray-100 dark:bg-meta-4 p-1 rounded border border-stroke dark:border-strokedark">
              <button
                onClick={() => setFilterMachineScope('ACTIVE')}
                className={`px-3 py-1 text-xs font-bold rounded transition flex items-center gap-1.5 ${filterMachineScope === 'ACTIVE'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white'
                  }`}
              >
                <Cpu className="h-3 w-3" />
                <span>Mesin {activeMachine} ({activeMachineProgramsCount})</span>
              </button>
              <button
                onClick={() => setFilterMachineScope('ALL')}
                className={`px-3 py-1 text-xs font-bold rounded transition ${filterMachineScope === 'ALL'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white'
                  }`}
              >
                <span>Semua Mesin ({programList.length})</span>
              </button>
            </div>

            {/* Filter Tipe Program */}
            <div className="flex items-center gap-1 bg-gray-100 dark:bg-meta-4 p-1 rounded border border-stroke dark:border-strokedark">
              <button
                onClick={() => setFilterType('ALL')}
                className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'ALL' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
              >
                Semua
              </button>
              <button
                onClick={() => setFilterType('MACHINE')}
                className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'MACHINE' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
              >
                Template
              </button>
              <button
                onClick={() => setFilterType('CUSTOM')}
                className={`px-3 py-1 text-xs font-bold rounded transition ${filterType === 'CUSTOM' ? 'bg-white dark:bg-boxdark text-primary shadow-sm' : 'text-gray-500'}`}
              >
                Custom
              </button>
            </div>
          </div>
        </div>

        {/* PROGRAM TABLE */}
        <div className="bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark overflow-hidden shadow-sm">
          <table className="w-full text-left text-xs text-gray-600 dark:text-gray-300">
            <thead className="bg-gray-50 dark:bg-meta-4 border-b border-stroke dark:border-strokedark text-black dark:text-white font-bold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4 w-20">Nomor</th>
                <th className="py-3 px-4 w-28">Mesin</th>
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
                  <td colSpan="7" className="py-8 text-center text-gray-400">
                    <div className="max-w-md mx-auto space-y-3 py-2">
                      <p className="text-slate-600 dark:text-slate-400 font-medium">
                        {searchTerm
                          ? `Tidak ada program yang sesuai dengan pencarian "${searchTerm}".`
                          : `Belum ada program yang terdaftar untuk Mesin ${activeMachine}.`}
                      </p>
                      <div className="flex flex-wrap items-center justify-center gap-2.5 pt-1">
                        <button
                          onClick={handleFetchProgramsFromMachine}
                          disabled={isFetchingFromMachine}
                          className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-sm transition disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Unduh Program dari Mesin {activeMachine} (FTP)</span>
                        </button>
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium border border-stroke dark:border-strokedark transition"
                        >
                          <Upload className="w-3.5 h-3.5 text-indigo-500" />
                          <span>Impor File .PRG</span>
                        </button>
                        <button
                          onClick={() => setFilterMachineScope('ALL')}
                          className="px-3 py-2 rounded-lg bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-300 text-xs font-medium transition"
                        >
                          Lihat Semua Program ({programList.length})
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredPrograms.map((prg) => (
                  <tr key={prg.program_number} className="hover:bg-gray-50 dark:hover:bg-meta-4/40 transition">
                    <td className="py-3 px-4 font-mono font-bold text-primary">
                      #{String(prg.program_number).padStart(4, '0')}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded font-mono text-[11px] font-bold bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-500/20">
                        <Cpu className="h-3 w-3 text-blue-500" />
                        {prg.machine_code || 'TD12'}
                      </span>
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
                          onClick={() => setFtpTransferModal(prg)}
                          className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 rounded border border-indigo-300 dark:border-indigo-800 transition"
                          title={`Tulis biner M_${String(prg.program_number).padStart(4, '0')}.PRG ke FTP Mesin ${prg.machine_code || activeMachine}`}
                        >
                          <Send className="h-3.5 w-3.5" />
                          <span>Tulis FTP</span>
                        </button>
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

        {/* MODAL BUAT PROGRAM BARU DENGAN PILIHAN MESIN */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-2xl max-w-lg w-full p-6 space-y-5 animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-primary/10 rounded text-primary">
                    <Plus className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-wider text-black dark:text-white">
                      Buat Program Resep Baru
                    </h3>
                    <p className="text-[11px] text-gray-500">Konfigurasi awal program dan penugasan mesin celup</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* PILIHAN MESIN */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1.5 flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-primary" />
                    <span>Pilih Mesin Target: <span className="text-rose-500">*</span></span>
                  </label>
                  <select
                    value={createMachineCode}
                    onChange={(e) => {
                      const chosen = e.target.value;
                      setCreateMachineCode(chosen);
                      if (createProgramName.startsWith('RESEP MESIN')) {
                        setCreateProgramName(`RESEP MESIN ${chosen}`);
                      }
                    }}
                    className="w-full text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 py-2.5 px-3 text-black dark:text-white outline-none focus:border-primary focus:bg-white dark:focus:bg-boxdark transition"
                  >
                    {availableMachines.map((m) => (
                      <option key={m.machine_no} value={m.machine_no} className="bg-white dark:bg-boxdark">
                        {m.machine_no} — {m.display_name || m.machine_no} {m.ip_address ? `(${m.ip_address})` : ''}
                      </option>
                    ))}
                  </select>
                  <p className="text-[10px] text-gray-400 mt-1">
                    Program akan dioptimalkan dan disinkronkan ke kontroler mesin ini.
                  </p>
                </div>

                {/* NOMOR & NAMA PROGRAM */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-1">
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1.5">
                      Nomor (ID):
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="9999"
                      value={createProgramNo}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        if (isNaN(val)) setCreateProgramNo(1);
                        else setCreateProgramNo(Math.min(Math.max(val, 1), 9999));
                      }}
                      className="w-full text-xs font-mono font-bold rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 py-2.5 px-3 text-black dark:text-white outline-none focus:border-primary focus:bg-white dark:focus:bg-boxdark transition"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1.5">
                      Nama Program / Resep:
                    </label>
                    <input
                      type="text"
                      maxLength={20}
                      value={createProgramName}
                      onChange={(e) => setCreateProgramName(e.target.value.toUpperCase())}
                      placeholder="Contoh: POLYESTER DARK 130C"
                      className="w-full text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4 py-2.5 px-3 text-black dark:text-white uppercase outline-none focus:border-primary focus:bg-white dark:focus:bg-boxdark transition"
                    />
                  </div>
                </div>

                {/* TEMPLATE AWAL */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-2">
                    Struktur Awal Langkah:
                  </label>
                  <div className="grid grid-cols-2 gap-2.5">
                    <label className={`flex flex-col p-3 rounded-lg border cursor-pointer transition ${createTemplateType === 'STANDARD' ? 'border-primary bg-primary/5 dark:bg-primary/10' : 'border-stroke dark:border-strokedark hover:bg-gray-50 dark:hover:bg-meta-4/40'}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-black dark:text-white">Standar 4-Langkah</span>
                        <input
                          type="radio"
                          name="createTemplate"
                          checked={createTemplateType === 'STANDARD'}
                          onChange={() => setCreateTemplateType('STANDARD')}
                          className="text-primary focus:ring-0"
                        />
                      </div>
                      <span className="text-[10px] text-gray-400">Start (F1) → Isi Air (F713) → Panas 98°C (F141) → End (F2)</span>
                    </label>

                    <label className={`flex flex-col p-3 rounded-lg border cursor-pointer transition ${createTemplateType === 'BLANK' ? 'border-primary bg-primary/5 dark:bg-primary/10' : 'border-stroke dark:border-strokedark hover:bg-gray-50 dark:hover:bg-meta-4/40'}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-black dark:text-white">Minimal Kosong</span>
                        <input
                          type="radio"
                          name="createTemplate"
                          checked={createTemplateType === 'BLANK'}
                          onChange={() => setCreateTemplateType('BLANK')}
                          className="text-primary focus:ring-0"
                        />
                      </div>
                      <span className="text-[10px] text-gray-400">Hanya Program Start (F1) & Program End (F2)</span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 dark:hover:bg-opacity-80 rounded-lg transition"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleConfirmCreateProgram}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded-lg shadow transition active:scale-95"
                >
                  <span>Buka Editor Program</span>
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL KONFIRMASI TRANSFER KE FTP KONTROLER */}
        {ftpTransferModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark shadow-2xl max-w-md w-full p-6 space-y-4 animate-in fade-in">
              <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-indigo-500/10 text-indigo-600 rounded-lg">
                    <Send className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-wider text-black dark:text-white">
                      Tulis Program ke FTP Kontroler
                    </h3>
                    <p className="text-[11px] text-gray-500">Kirim file biner .PRG langsung ke SETEX 777</p>
                  </div>
                </div>
                <button onClick={() => setFtpTransferModal(null)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="bg-gray-50 dark:bg-meta-4/40 p-4 rounded-lg border border-stroke dark:border-strokedark space-y-2.5 text-xs">
                <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                  <span className="text-gray-500 font-medium">Program Target:</span>
                  <strong className="text-black dark:text-white font-mono">
                    M_{String(ftpTransferModal.program_number).padStart(4, '0')}.PRG ({ftpTransferModal.program_name})
                  </strong>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                  <span className="text-gray-500 font-medium">Mesin Target:</span>
                  <span className="font-bold text-primary font-mono">
                    Mesin {ftpTransferModal.machine_code || activeMachine}
                  </span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                  <span className="text-gray-500 font-medium">IP Controller:</span>
                  <span className="font-mono font-bold text-emerald-600">
                    {availableMachines.find(m => m.machine_no === (ftpTransferModal.machine_code || activeMachine))?.ip_address || '172.16.110.101'}:21
                  </span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                  <span className="text-gray-500 font-medium">Model HMI & Direktori:</span>
                  <select
                    value={controllerModel}
                    onChange={(e) => handleSelectControllerModel(e.target.value)}
                    className="font-mono text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded px-2 py-1 outline-none"
                  >
                    <option value="777">SECOM 777 (/Storage/sc777ce/Programs)</option>
                    <option value="797">SECOM 797 (/Flashdisk/SC797CE/Programs)</option>
                  </select>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 font-medium">Target Path FTP:</span>
                  <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                    {currentRemoteDir}
                  </span>
                </div>
              </div>

              <p className="text-[11px] text-gray-500">
                File biner M_{String(ftpTransferModal.program_number).padStart(4, '0')}.PRG akan langsung disimpan ke storage kontroler mesin ini ({controllerModel === '797' ? 'SETEX 797' : 'SETEX 777'}) dan siap dijalankan oleh operator pada HMI. Sistem juga memiliki fitur auto-fallback jika folder 777/797 tidak ditemukan.
              </p>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setFtpTransferModal(null)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 rounded-lg transition"
                >
                  Batal
                </button>
                <button
                  type="button"
                  disabled={isTransferringFtp}
                  onClick={() => handleTransferToFtp(ftpTransferModal.program_number, ftpTransferModal.machine_code || activeMachine)}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow transition active:scale-95 disabled:opacity-50"
                >
                  <Send className={`h-4 w-4 ${isTransferringFtp ? 'animate-spin' : ''}`} />
                  <span>{isTransferringFtp ? 'Sedang Mentransfer...' : `Tulis Sekarang ke FTP Mesin ${ftpTransferModal.machine_code || activeMachine}`}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // =========================================================================
  // RENDER VIEW 2: LINEAR STEP SEQUENCE EDITOR (PRG STUDIO)
  // =========================================================================
  const mainFn = currentStep?.functions?.find(f => f.column === 1);
  const mainFnMeta = mainFn ? getFunctionMeta(mainFn.function_id, machineFunctions) : null;
  const fDef = mainFn ? ((machineFunctions && machineFunctions[String(mainFn.function_id)]) || ALL_FUNCTIONS[String(mainFn.function_id)]) : null;
  const parallelFns = currentStep?.functions?.filter(f => f.column > 1) || [];

  return (
    <div className="space-y-5">
      {/* NOTIFICATION */}
      {notification && (
        <div className={`flex items-center justify-between p-4 rounded-md border shadow-sm ${notification.type === 'success'
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

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 bg-primary/10 border border-primary/20 rounded px-2 py-0.5" title="Nomor Program SETEX (1 - 9999)">
                  <span className="text-xs font-bold font-mono text-primary">ID:</span>
                  <input
                    type="number"
                    min="1"
                    max="9999"
                    value={programNo}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      if (!isNaN(v)) setProgramNo(v);
                    }}
                    className={`w-14 text-xs font-bold font-mono bg-transparent outline-none ${
                      programNo > 9999 || programNo < 1 ? 'text-red-500 underline font-black' : 'text-primary'
                    }`}
                  />
                </div>
                <input
                  type="text"
                  value={programName}
                  onChange={(e) => setProgramName(e.target.value.toUpperCase())}
                  className="text-base font-black text-black dark:text-white uppercase tracking-wider bg-transparent border-b border-dashed border-gray-400 focus:border-primary outline-none px-1"
                  placeholder="NAMA PROGRAM RESEP"
                  maxLength={20}
                />
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-gray-400 font-mono">
                  Target: M_{String(programNo > 9999 ? 9999 : programNo).padStart(4, '0')}.PRG · {steps.length} Langkah
                </span>
                {(programNo > 9999 || programNo < 1) && (
                  <span className="text-[10px] font-bold text-red-600 bg-red-100 dark:bg-red-950/60 px-1.5 py-0.2 rounded border border-red-300">
                    Maks. 9999 (SETEX 4 Digit)!
                  </span>
                )}
              </div>
            </div>

            {/* Pilihan Mesin pada Editor */}
            <div className="flex items-center gap-2 bg-gray-50 dark:bg-meta-4/60 px-3 py-1.5 rounded-lg border border-stroke dark:border-strokedark shadow-xs">
              <Cpu className="h-4 w-4 text-primary shrink-0" />
              <div className="flex flex-col">
                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-400">Pilihan Mesin:</span>
                <select
                  value={machineCode}
                  onChange={(e) => setMachineCode(e.target.value)}
                  className="text-xs font-bold font-mono bg-transparent text-primary dark:text-emerald-400 outline-none cursor-pointer"
                >
                  {availableMachines.map((m) => (
                    <option key={m.machine_no} value={m.machine_no} className="bg-white dark:bg-boxdark text-black dark:text-white">
                      {m.machine_no} — {m.display_name || m.machine_no}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* ACTIONS */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowWizardModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded shadow-sm transition active:scale-95"
            title="Buka Wizard Cepat untuk menyusun resep komplit beserta seluruh sub-programnya"
          >
            <Wand2 className="h-3.5 w-3.5" />
            <span>Wizard Cepat</span>
          </button>

          <button
            onClick={() => setShowSubProgramDrawer(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30 rounded shadow-sm hover:bg-indigo-100 transition active:scale-95"
            title="Pilih dan sisipkan modul fasa / sub-program dari katalog"
          >
            <BookOpen className="h-3.5 w-3.5 text-indigo-500" />
            <span>+ Tambah Fasa (Sub)</span>
          </button>

          <button
            onClick={() => setShowTemplateModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-500/30 rounded shadow-sm hover:bg-amber-100 transition"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            <span>Template Mesin</span>
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
            onClick={() => handleTransferToFtp(programNo, machineCode)}
            disabled={isTransferringFtp}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded shadow-sm transition active:scale-95 disabled:opacity-50"
            title={`Tulis biner M_${String(programNo).padStart(4, '0')}.PRG langsung ke FTP Kontroler Mesin ${machineCode}`}
          >
            <Send className={`h-3.5 w-3.5 ${isTransferringFtp ? 'animate-spin' : ''}`} />
            <span>{isTransferringFtp ? 'Menulis ke FTP...' : `Tulis ke FTP Mesin (${machineCode})`}</span>
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

      {/* PROCESS PIPELINE BAR (HORIZONTAL SUB-PROGRAM VIEW) */}
      <ProcessPipelineBar
        subPrograms={subPrograms}
        activeSubIdx={activeSubIdx}
        onSelectSub={(subIdx) => {
          setActiveSubIdx(subIdx);
          let targetStep = 1;
          for (let i = 0; i < subIdx; i++) {
            targetStep += subPrograms[i].steps?.length || 0;
          }
          if (targetStep < steps.length) {
            setSelectedStepIdx(targetStep);
          }
          const targetSub = subPrograms[subIdx];
          if (targetSub) {
            setExpandedSubIds(prev => new Set([...prev, targetSub.id || subIdx]));
          }
        }}
        onMoveSub={handleMoveSubProgram}
        onDuplicateSub={handleDuplicateSubProgram}
        onDeleteSub={handleDeleteSubProgram}
        onOpenDrawer={() => setShowSubProgramDrawer(true)}
        onOpenWizard={() => setShowWizardModal(true)}
        isGroupedView={isGroupedView}
        onToggleGroupedView={(val) => setIsGroupedView(val)}
      />

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

        {/* KOLOM KIRI: DAFTAR LANGKAH LINEAR ATAU GRUP FASA (5 COLS) */}
        <div className="lg:col-span-5 bg-white dark:bg-boxdark rounded-lg border border-stroke dark:border-strokedark shadow-sm overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 dark:bg-meta-4/30 border-b border-stroke dark:border-strokedark flex items-center justify-between">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-black dark:text-white flex items-center gap-1.5">
                <Boxes className="h-4 w-4 text-primary" />
                Urutan Langkah ({steps.length})
                {isGroupedView && (
                  <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-1.5 py-0.2 rounded border border-indigo-200 dark:border-indigo-800">
                    {subPrograms.length} Fasa
                  </span>
                )}
              </span>
            </div>
            
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setShowSubProgramDrawer(true)}
                className="flex items-center gap-1 px-2 py-1 text-xs font-bold bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 text-indigo-700 dark:text-indigo-300 rounded border border-indigo-200 dark:border-indigo-800 transition"
                title="Sisipkan modul fasa baru"
              >
                <Plus className="h-3 w-3" />
                <span>+ Fasa</span>
              </button>

              <button
                onClick={handleAddStep}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold bg-primary hover:bg-primary/90 text-white rounded shadow-sm transition"
              >
                <Plus className="h-3 w-3" />
                <span>+ Langkah</span>
              </button>
            </div>
          </div>

          {/* VIEW MODE: GROUPED HIERARCHICAL ACCORDION */}
          {isGroupedView ? (
            <div className="divide-y divide-stroke dark:divide-strokedark max-h-[650px] overflow-y-auto p-2 space-y-2">
              {/* STEP 1: PROGRAM START (PINNED) */}
              {steps.length > 0 && (
                <div
                  onClick={() => setSelectedStepIdx(0)}
                  className={`p-2.5 rounded-lg border transition cursor-pointer flex items-center justify-between ${
                    selectedStepIdx === 0
                      ? 'border-emerald-500 bg-emerald-50/80 dark:bg-emerald-950/40 ring-1 ring-emerald-500'
                      : 'border-stroke dark:border-strokedark bg-slate-50/60 dark:bg-meta-4/20 hover:bg-slate-100 dark:hover:bg-meta-4/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300 font-mono text-[10px] font-bold flex items-center justify-center">
                      01
                    </span>
                    <div>
                      <span className="text-xs font-bold text-black dark:text-white flex items-center gap-1.5">
                        <FileCode className="h-3.5 w-3.5 text-emerald-600" />
                        Program Start (Mulai Siklus Mesin)
                      </span>
                      <p className="text-[10px] text-gray-400 font-mono">F1 · Pengunci awal siklus SECOM</p>
                    </div>
                  </div>
                  <ChevronRight className={`h-3.5 w-3.5 ${selectedStepIdx === 0 ? 'text-emerald-600' : 'text-gray-300'}`} />
                </div>
              )}

              {/* SUB-PROGRAM ACCORDION CARDS */}
              {subPrograms.map((sub, sIdx) => {
                const isExpanded = expandedSubIds.has(sub.id || sIdx);
                const isSubActive = activeSubIdx === sIdx;
                const catClass = (sub.category === 'Pretreatment') ? 'border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-950/20'
                  : (sub.category === 'Dyeing') ? 'border-indigo-300 dark:border-indigo-700 bg-indigo-50/50 dark:bg-indigo-950/20'
                  : (sub.category === 'Washing') ? 'border-rose-300 dark:border-rose-700 bg-rose-50/50 dark:bg-rose-950/20'
                  : (sub.category === 'Rinse') ? 'border-cyan-300 dark:border-cyan-700 bg-cyan-50/50 dark:bg-cyan-950/20'
                  : 'border-stroke dark:border-strokedark bg-gray-50/50 dark:bg-meta-4/20';

                return (
                  <div
                    key={sub.id || `${sub.treatment_number}-${sIdx}`}
                    className={`rounded-xl border transition-all overflow-hidden ${catClass} ${
                      isSubActive ? 'ring-2 ring-primary/80 shadow-xs' : ''
                    }`}
                  >
                    {/* SUB-PROGRAM ACCORDION HEADER */}
                    <div
                      onClick={() => {
                        setActiveSubIdx(sIdx);
                        setExpandedSubIds(prev => {
                          const next = new Set(prev);
                          if (next.has(sub.id || sIdx)) next.delete(sub.id || sIdx);
                          else next.add(sub.id || sIdx);
                          return next;
                        });
                      }}
                      className="p-3 cursor-pointer flex items-center justify-between select-none hover:bg-black/5 dark:hover:bg-white/5 transition"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <button
                          type="button"
                          className="text-gray-400 hover:text-black dark:hover:text-white p-0.5"
                        >
                          {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                        <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 text-[10px] font-mono font-bold flex items-center justify-center shrink-0">
                          {sIdx + 1}
                        </span>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-black dark:text-white truncate">
                              {sub.treatment_name || sub.name}
                            </span>
                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded-full border bg-white dark:bg-boxdark border-stroke dark:border-strokedark text-gray-600 dark:text-gray-300 shrink-0">
                              {sub.category || 'Process'}
                            </span>
                          </div>
                          <span className="text-[10px] text-gray-400 font-mono block">
                            {sub.steps ? sub.steps.length : 0} Langkah Mikro
                          </span>
                        </div>
                      </div>

                      {/* Header Actions */}
                      <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          disabled={sIdx === 0}
                          onClick={() => handleMoveSubProgram(sIdx, 'UP')}
                          className="p-1 text-gray-400 hover:text-black dark:hover:text-white disabled:opacity-20"
                          title="Geser Fasa Naik"
                        >
                          <ArrowUp className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          disabled={sIdx === subPrograms.length - 1}
                          onClick={() => handleMoveSubProgram(sIdx, 'DOWN')}
                          className="p-1 text-gray-400 hover:text-black dark:hover:text-white disabled:opacity-20"
                          title="Geser Fasa Turun"
                        >
                          <ArrowDown className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDuplicateSubProgram(sIdx)}
                          className="p-1 text-blue-500 hover:text-blue-700"
                          title="Duplikasi Fasa Ini"
                        >
                          <Copy className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSubProgram(sIdx)}
                          className="p-1 text-rose-500 hover:text-rose-700"
                          title="Hapus Fasa Ini"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* SUB-PROGRAM MICRO STEPS (INSIDE ACCORDION) */}
                    {isExpanded && (
                      <div className="p-2 space-y-1.5 bg-white/70 dark:bg-boxdark/70 border-t border-stroke/70 dark:border-strokedark/70">
                        {(sub.steps || []).map((st, stepInSubIdx) => {
                          // Compute matching global step index
                          let globalStepIdx = 1;
                          for (let i = 0; i < sIdx; i++) {
                            globalStepIdx += subPrograms[i].steps?.length || 0;
                          }
                          globalStepIdx += stepInSubIdx;

                          const matchingStep = steps[globalStepIdx] || st;
                          const mFn = matchingStep.functions?.find(f => f.column === 1);
                          const meta = mFn ? getFunctionMeta(mFn.function_id) : null;
                          const isSelected = selectedStepIdx === globalStepIdx;
                          const params = mFn?.params || [];

                          let badgeText = '';
                          if (mFn?.function_id === 141) badgeText = `${params[0] || 0} °C · ${params[2] || 0}m`;
                          else if (mFn?.function_id === 713) badgeText = `${params[1] || 0} L`;
                          else if (mFn?.function_id === 71) badgeText = `Drain ${params[0] || 0}%`;

                          return (
                            <div
                              key={stepInSubIdx}
                              onClick={() => {
                                setSelectedStepIdx(globalStepIdx);
                                setActiveSubIdx(sIdx);
                              }}
                              className={`p-2 rounded-lg border transition cursor-pointer flex items-center justify-between text-xs ${
                                isSelected
                                  ? 'bg-primary/10 border-primary text-primary font-bold shadow-xs'
                                  : 'bg-white dark:bg-boxdark border-stroke dark:border-strokedark hover:bg-gray-50 dark:hover:bg-meta-4/40 text-black dark:text-white'
                              }`}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="w-5 h-5 rounded bg-gray-100 dark:bg-meta-4 text-gray-700 dark:text-gray-300 font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                                  {String(globalStepIdx + 1).padStart(2, '0')}
                                </span>
                                <div className="min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="truncate">
                                      {meta?.name || matchingStep.label || `Langkah ${globalStepIdx + 1}`}
                                    </span>
                                    {badgeText && (
                                      <span className="text-[9px] font-mono font-bold px-1 py-0.2 bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 rounded border border-blue-500/20 shrink-0">
                                        {badgeText}
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-[10px] text-gray-400 truncate max-w-[190px]">
                                    {matchingStep.label || 'Tanpa komentar'}
                                  </p>
                                </div>
                              </div>

                              <ChevronRight className={`h-3.5 w-3.5 shrink-0 ${isSelected ? 'text-primary' : 'text-gray-300'}`} />
                            </div>
                          );
                        })}

                        {/* Add Step directly in this Sub-Program */}
                        <button
                          type="button"
                          onClick={() => handleAddStepToSubProgram(sIdx)}
                          className="w-full mt-1.5 py-1 px-2 text-[11px] font-semibold text-primary dark:text-blue-400 hover:bg-primary/5 rounded border border-dashed border-primary/30 flex items-center justify-center gap-1 transition"
                        >
                          <Plus className="h-3 w-3" />
                          <span>Tambah Langkah di {sub.treatment_name || 'Fasa Ini'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}

              {/* STEP END (PINNED AT BOTTOM) */}
              {steps.length > 1 && (
                <div
                  onClick={() => setSelectedStepIdx(steps.length - 1)}
                  className={`p-2.5 rounded-lg border transition cursor-pointer flex items-center justify-between ${
                    selectedStepIdx === steps.length - 1
                      ? 'border-slate-500 bg-slate-50/80 dark:bg-slate-900/60 ring-1 ring-slate-500'
                      : 'border-stroke dark:border-strokedark bg-slate-50/60 dark:bg-meta-4/20 hover:bg-slate-100 dark:hover:bg-meta-4/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-300 font-mono text-[10px] font-bold flex items-center justify-center">
                      {String(steps.length).padStart(2, '0')}
                    </span>
                    <div>
                      <span className="text-xs font-bold text-black dark:text-white flex items-center gap-1.5">
                        <FileCode className="h-3.5 w-3.5 text-slate-600" />
                        Program End (Selesai Siklus)
                      </span>
                      <p className="text-[10px] text-gray-400 font-mono">F2 · Pengunci akhir siklus SECOM</p>
                    </div>
                  </div>
                  <ChevronRight className={`h-3.5 w-3.5 ${selectedStepIdx === steps.length - 1 ? 'text-slate-600' : 'text-gray-300'}`} />
                </div>
              )}

              {/* Bottom Quick Insert Sub-Program Button */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowSubProgramDrawer(true)}
                  className="w-full py-2 px-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 hover:bg-indigo-100 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs transition"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>+ Sisipkan Modul Fasa / Sub-Program Baru</span>
                </button>
              </div>
            </div>
          ) : (
            /* VIEW MODE: FLAT LINEAR LIST (ORIGINAL VIEW) */
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
                    className={`p-3 cursor-pointer transition flex items-center justify-between ${isSelected
                      ? 'bg-primary/10 border-l-4 border-primary'
                      : 'hover:bg-gray-50 dark:hover:bg-meta-4/30'
                      }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`w-6 h-6 rounded flex items-center justify-center font-mono text-xs font-bold ${isStart || isEnd ? 'bg-gray-200 dark:bg-meta-4 text-gray-700 dark:text-gray-300' : 'bg-primary text-white'
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
          )}
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
                      const paramDef = (machineParameters && machineParameters[String(pMeta.definition_id)]) || ALL_PARAMETERS[String(pMeta.definition_id)];
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
                        {parallelOptions.map(pf => (
                          <option key={`${pf.id}-${pf.col}`} value={`${pf.id},${pf.col}`}>
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
                        const fMeta = getFunctionMeta(fn.function_id, machineFunctions);
                        const subDef = (machineFunctions && machineFunctions[String(fn.function_id)]) || ALL_FUNCTIONS[String(fn.function_id)];

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
                                  const paramDef = (machineParameters && machineParameters[String(pMeta.definition_id)]) || ALL_PARAMETERS[String(pMeta.definition_id)];
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
              <div className={`p-3.5 rounded-lg border text-xs ${validationIssues.length === 0
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

      {/* SUB-PROGRAM READY-TO-USE DRAWER */}
      <SubProgramDrawer
        isOpen={showSubProgramDrawer}
        onClose={() => setShowSubProgramDrawer(false)}
        onInsertSubProgram={handleInsertSubProgramFromDrawer}
        subProgramsCount={subPrograms.length}
      />

      {/* SMART RECIPE WIZARD MODAL */}
      <SmartRecipeWizardModal
        isOpen={showWizardModal}
        onClose={() => setShowWizardModal(false)}
        onApplyRecipe={handleApplyWizardRecipe}
        availableMachines={availableMachines}
        activeMachine={activeMachine}
      />
    </div>
  );
}
