import React, { useState, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import {
  Layers,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Save,
  Download,
  Play,
  Settings2,
  Flame,
  Droplet,
  Clock,
  Gauge,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Search,
  Copy,
  RefreshCw,
  FileCode,
  ExternalLink,
  Sparkles,
  ArrowLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Eye,
  BookOpen,
  Info,
  Server,
  Zap,
  Boxes,
  Cpu,
  Send,
  Upload,
  X
} from 'lucide-react';
import TempCurveChart from '../components/Charts/TempCurveChart';

// Category color mappings
const CATEGORY_COLORS = {
  Pretreatment: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700',
  Dyeing: 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-700',
  Washing: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-700',
  Neutralization: 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-700',
  Rinse: 'bg-cyan-100 text-cyan-800 border-cyan-300 dark:bg-cyan-950/40 dark:text-cyan-300 dark:border-cyan-700',
  Finishing: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700',
  End: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-900/60 dark:text-slate-300 dark:border-slate-700',
  Custom: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-700',
  General: 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'
};

export default function OrgatexEdxProgram() {
  // Navigation / View State
  const [viewMode, setViewMode] = useState('LIST'); // 'LIST' | 'EDITOR'

  // Active Selected Machine (Synchronized across OrgaTEX & SETEX Studio)
  const [activeMachine, setActiveMachine] = useState(() => {
    return localStorage.getItem('selected_dyeing_machine') || 'TD12';
  });
  const [filterMachineScope, setFilterMachineScope] = useState('ACTIVE'); // 'ACTIVE' | 'ALL'
  const [machineList, setMachineList] = useState([]);

  // FTP Transfer Modal State
  const [ftpTransferModal, setFtpTransferModal] = useState(null);
  const [isTransferringFtp, setIsTransferringFtp] = useState(false);

  // Program List State
  const [programList, setProgramList] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Treatment Library State
  const [treatmentsLibrary, setTreatmentsLibrary] = useState([]);
  const [loadingTreatments, setLoadingTreatments] = useState(false);
  const [showLibraryModal, setShowLibraryModal] = useState(false);
  const [treatmentFilterCategory, setTreatmentFilterCategory] = useState('ALL');

  // Editor State (Procedure = Level 1)
  const [programNo, setProgramNo] = useState(101);
  const [programName, setProgramName] = useState('COTTON REACTIVE DARK 60C');
  const [machineCode, setMachineCode] = useState(() => {
    return localStorage.getItem('selected_dyeing_machine') || 'TD12';
  });
  const [controllerModel, setControllerModel] = useState(() => {
    const savedM = localStorage.getItem('selected_dyeing_machine') || 'TD12';
    return localStorage.getItem('controller_model_' + savedM) || '777';
  });
  const [procedureTreatments, setProcedureTreatments] = useState([]); // List of Treatment Items
  const [selectedPosition, setSelectedPosition] = useState(0); // 0-based index
  const [isSaving, setIsSaving] = useState(false);
  const [showCurveChart, setShowCurveChart] = useState(true);

  // Flattened steps preview modal
  const [showFlattenedModal, setShowFlattenedModal] = useState(false);
  const [notification, setNotification] = useState(null);

  // 1. Fetch Master Programs List
  const fetchProgramList = async () => {
    setLoadingList(true);
    try {
      const res = await axios.get('/api/programs/');
      setProgramList(res.data || []);
    } catch (err) {
      console.error('Gagal memuat program list:', err);
    } finally {
      setLoadingList(false);
    }
  };

  // 2. Fetch Treatment Library (Sub-Programs Level 2)
  const fetchTreatmentsLibrary = async () => {
    setLoadingTreatments(true);
    try {
      const res = await axios.get('/api/programs/treatments/');
      setTreatmentsLibrary(res.data || []);
    } catch (err) {
      console.error('Gagal memuat treatment library:', err);
    } finally {
      setLoadingTreatments(false);
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
      console.error('Gagal memuat machine list:', err);
    }
  };

  useEffect(() => {
    fetchProgramList();
    fetchTreatmentsLibrary();
    fetchMachines();
  }, []);

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
  const handleTransferToFtp = async (pNo, mCode) => {
    const targetM = (mCode || activeMachine).trim().toUpperCase();
    const targetObj = availableMachines.find(m => m.machine_no.toUpperCase() === targetM) || selectedMachineObj;
    setIsTransferringFtp(true);
    try {
      const res = await axios.post(`/api/programs/transfer-ftp/${pNo}`, {
        machine_code: targetM,
        ip_address: targetObj?.ip_address,
        controller_type: controllerModel,
        target_dir: currentRemoteDir,
        timeout: 6.0
      });
      showToast(res.data.message || `Program M_${String(pNo).padStart(4, '0')}.PRG berhasil ditulis ke FTP Kontroler Mesin ${targetM}!`);
      setFtpTransferModal(null);
    } catch (err) {
      showToast(err.response?.data?.detail || err.message, 'error');
    } finally {
      setIsTransferringFtp(false);
    }
  };

  // Count programs for active machine
  const activeMachineProgramsCount = useMemo(() => {
    return programList.filter(p => (p.machine_code || 'TD12').toUpperCase() === activeMachine.toUpperCase()).length;
  }, [programList, activeMachine]);

  const showToast = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4500);
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
      showToast(res.data.message || `Pemeriksaan program Mesin ${activeMachine} selesai!`, res.data.success ? 'success' : 'error');
      await fetchProgramList();
      setFilterMachineScope('ACTIVE');
    } catch (err) {
      showToast(err.response?.data?.detail || err.message, 'error');
    } finally {
      setIsFetchingFromMachine(false);
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
        showToast(res.data.message || `File ${file.name} berhasil diimpor untuk Mesin ${activeMachine}!`);
        await fetchProgramList();
        setFilterMachineScope('ACTIVE');
      } catch (err) {
        showToast(err.response?.data?.detail || err.message, 'error');
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  // 3. Open Existing Program in EDX300 Builder
  const handleOpenProgram = async (pno) => {
    try {
      const res = await axios.get(`/api/programs/${pno}`);
      const data = res.data;
      setProgramNo(data.program_no || pno);
      setProgramName(data.program_name || `PROGRAM #${pno}`);
      setMachineCode(data.machine_code || activeMachine);

      if (data.sub_programs && data.sub_programs.length > 0) {
        setProcedureTreatments(data.sub_programs);
      } else if (data.steps && data.steps.length > 0) {
        // Group raw SECOM bytecode steps into logical treatments (Pretreatment, Dyeing, Soaping, Rinse)
        const rawSteps = data.steps;
        const treatments = [];
        let curSteps = [];
        let curCategory = 'Pretreatment';
        let pos = 1;

        rawSteps.forEach((s) => {
          const fids = (s.functions || []).map(f => f.function_id);
          let cat = curCategory;
          if (fids.includes(141)) {
            const temp = s.summary_temp || 0;
            if (temp >= 85 && pos > 2) cat = 'Washing';
            else if (temp >= 50) cat = 'Dyeing';
            else cat = 'Pretreatment';
          } else if (fids.includes(71)) {
            cat = 'Rinse';
          } else if (fids.includes(2) || fids.includes(122)) {
            cat = 'End';
          }

          if (curSteps.length > 0 && cat !== curCategory && curSteps.length >= 3) {
            treatments.push({
              position: pos++,
              treatment_name: `${curCategory} (Langkah ${curSteps[0].step_no} - ${curSteps[curSteps.length - 1].step_no})`,
              category: curCategory,
              parameters: {
                temperature: curSteps.find(st => st.summary_temp)?.summary_temp || 60,
                hold_time: curSteps.reduce((acc, st) => acc + (st.summary_time_min || 0), 0) || 30,
                pump_speed: 85,
                water_level: 3000
              },
              steps: [...curSteps]
            });
            curSteps = [];
            curCategory = cat;
          }
          curSteps.push(s);
        });

        if (curSteps.length > 0) {
          treatments.push({
            position: pos++,
            treatment_name: `${curCategory} (Langkah ${curSteps[0].step_no} - ${curSteps[curSteps.length - 1].step_no})`,
            category: curCategory,
            parameters: {
              temperature: curSteps.find(st => st.summary_temp)?.summary_temp || 60,
              hold_time: curSteps.reduce((acc, st) => acc + (st.summary_time_min || 0), 0) || 30,
              pump_speed: 85,
              water_level: 3000
            },
            steps: [...curSteps]
          });
        }

        setProcedureTreatments(treatments);
      } else {
        // If it's a flat program without explicit sub_programs, create default treatments
        if (treatmentsLibrary.length > 0) {
          const defaultSeq = [
            {
              position: 1,
              treatment_id: treatmentsLibrary[0].id,
              treatment_number: treatmentsLibrary[0].number,
              treatment_name: treatmentsLibrary[0].name,
              category: treatmentsLibrary[0].category || 'Pretreatment',
              parameters: { ...treatmentsLibrary[0].parameters },
              steps: treatmentsLibrary[0].steps || []
            },
            {
              position: 2,
              treatment_id: treatmentsLibrary[1]?.id || 2,
              treatment_number: treatmentsLibrary[1]?.number || 'TR-DYE-REACT',
              treatment_name: treatmentsLibrary[1]?.name || 'Pencelupan Reaktif 60C',
              category: treatmentsLibrary[1]?.category || 'Dyeing',
              parameters: { ...treatmentsLibrary[1]?.parameters },
              steps: treatmentsLibrary[1]?.steps || []
            },
            {
              position: 3,
              treatment_id: treatmentsLibrary[3]?.id || 4,
              treatment_number: treatmentsLibrary[3]?.number || 'TR-SOAP',
              treatment_name: treatmentsLibrary[3]?.name || 'Pencucian Sabun 95C',
              category: treatmentsLibrary[3]?.category || 'Washing',
              parameters: { ...treatmentsLibrary[3]?.parameters },
              steps: treatmentsLibrary[3]?.steps || []
            },
            {
              position: 4,
              treatment_id: treatmentsLibrary[5]?.id || 6,
              treatment_number: treatmentsLibrary[5]?.number || 'TR-RINSE',
              treatment_name: treatmentsLibrary[5]?.name || 'Pembilasan Dingin',
              category: treatmentsLibrary[5]?.category || 'Rinse',
              parameters: { ...treatmentsLibrary[5]?.parameters },
              steps: treatmentsLibrary[5]?.steps || []
            }
          ];
          setProcedureTreatments(defaultSeq);
        }
      }
      setSelectedPosition(0);
      setViewMode('EDITOR');
    } catch (err) {
      console.error('Gagal mengambil detail program:', err);
      showToast(`Gagal membuka program #${pno}`, 'error');
    }
  };

  // 4. Create New Blank Procedure
  const handleCreateNewProcedure = () => {
    const nextNo = programList.length > 0 ? Math.max(...programList.map(p => p.program_number || 0)) + 1 : 101;
    setProgramNo(nextNo);
    setProgramName(`ORGATEX RESEP MESIN ${activeMachine}`);
    setMachineCode(activeMachine);

    // Seed with standard sequence: Scouring -> Dyeing -> Soaping -> Rinse
    if (treatmentsLibrary.length >= 4) {
      const initSeq = [
        {
          position: 1,
          treatment_id: treatmentsLibrary[0].id,
          treatment_number: treatmentsLibrary[0].number,
          treatment_name: treatmentsLibrary[0].name,
          category: treatmentsLibrary[0].category || 'Pretreatment',
          parameters: { ...treatmentsLibrary[0].parameters },
          steps: treatmentsLibrary[0].steps || []
        },
        {
          position: 2,
          treatment_id: treatmentsLibrary[1].id,
          treatment_number: treatmentsLibrary[1].number,
          treatment_name: treatmentsLibrary[1].name,
          category: treatmentsLibrary[1].category || 'Dyeing',
          parameters: { ...treatmentsLibrary[1].parameters },
          steps: treatmentsLibrary[1].steps || []
        },
        {
          position: 3,
          treatment_id: treatmentsLibrary[3].id,
          treatment_number: treatmentsLibrary[3].number,
          treatment_name: treatmentsLibrary[3].name,
          category: treatmentsLibrary[3].category || 'Washing',
          parameters: { ...treatmentsLibrary[3].parameters },
          steps: treatmentsLibrary[3].steps || []
        },
        {
          position: 4,
          treatment_id: treatmentsLibrary[5].id,
          treatment_number: treatmentsLibrary[5].number,
          treatment_name: treatmentsLibrary[5].name,
          category: treatmentsLibrary[5].category || 'Rinse',
          parameters: { ...treatmentsLibrary[5].parameters },
          steps: treatmentsLibrary[5].steps || []
        }
      ];
      setProcedureTreatments(initSeq);
    } else {
      setProcedureTreatments([]);
    }
    setSelectedPosition(0);
    setViewMode('EDITOR');
  };

  // 5. Add Treatment from Library into Procedure
  const handleAddTreatmentToProcedure = (treatment) => {
    const newPos = procedureTreatments.length + 1;
    const newItem = {
      position: newPos,
      treatment_id: treatment.id,
      treatment_number: treatment.number,
      treatment_name: treatment.name,
      category: treatment.category || 'General',
      parameters: { ...(treatment.parameters || {}) },
      steps: treatment.steps || []
    };
    setProcedureTreatments([...procedureTreatments, newItem]);
    setSelectedPosition(procedureTreatments.length);
    setShowLibraryModal(false);
    showToast(`Treatment "${treatment.name}" ditambahkan ke Posisi #${newPos}`);
  };

  // 6. Remove Treatment from Procedure
  const handleRemoveTreatment = (index) => {
    if (procedureTreatments.length <= 1) {
      showToast('Procedure minimal harus memiliki 1 Treatment!', 'error');
      return;
    }
    const updated = procedureTreatments.filter((_, idx) => idx !== index).map((item, idx) => ({
      ...item,
      position: idx + 1
    }));
    setProcedureTreatments(updated);
    if (selectedPosition >= updated.length) {
      setSelectedPosition(updated.length - 1);
    }
  };

  // 7. Move Treatment Position Up/Down
  const handleMoveTreatment = (index, direction) => {
    const newIdx = direction === 'UP' ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= procedureTreatments.length) return;

    const copy = [...procedureTreatments];
    const temp = copy[index];
    copy[index] = copy[newIdx];
    copy[newIdx] = temp;

    const renumbered = copy.map((item, idx) => ({
      ...item,
      position: idx + 1
    }));

    setProcedureTreatments(renumbered);
    setSelectedPosition(newIdx);
  };

  // 8. Update Overridden Parameter in Active Treatment
  const handleUpdateParameter = (paramKey, value) => {
    if (procedureTreatments.length === 0) return;
    const copy = [...procedureTreatments];
    const active = copy[selectedPosition];
    if (!active) return;

    const currentParams = { ...(active.parameters || {}) };
    currentParams[paramKey] = parseFloat(value) || 0;

    copy[selectedPosition] = {
      ...active,
      parameters: currentParams
    };
    setProcedureTreatments(copy);
  };

  // 9. Compute Flattened SECOM Steps in real-time
  const flattenedSteps = useMemo(() => {
    const result = [];
    let stepCount = 1;

    procedureTreatments.forEach((tr, trIdx) => {
      const p = tr.parameters || {};
      const baseSteps = tr.steps || [];

      baseSteps.forEach((s) => {
        const funcs = (s.functions || []).map((fn) => {
          const pVals = [...(fn.params || [])];
          // Inject overrides
          if (fn.function_id === 141 && 'temperature' in p) {
            pVals[0] = p.temperature;
            if ('gradient' in p && pVals.length > 1) pVals[1] = p.gradient;
          } else if (fn.function_id === 121 && 'hold_time' in p) {
            pVals[0] = p.hold_time;
          } else if (fn.function_id === 713 && 'water_level' in p) {
            if (pVals.length > 1) pVals[1] = p.water_level;
            else if (pVals.length === 1) pVals.push(p.water_level);
          } else if (fn.function_id === 404 && 'pump_speed' in p) {
            pVals[0] = p.pump_speed;
          }

          return {
            ...fn,
            params: pVals
          };
        });

        let sTemp = s.summary_temp;
        let sTime = s.summary_time_min;
        let sWater = s.summary_water_l;
        let sPump = s.summary_pump_pct;

        if (funcs.some(f => f.function_id === 141) && 'temperature' in p) {
          sTemp = p.temperature;
        }
        if (funcs.some(f => f.function_id === 121) && 'hold_time' in p) {
          sTime = p.hold_time;
        }
        if (funcs.some(f => f.function_id === 713) && 'water_level' in p) {
          sWater = p.water_level;
        }
        if (funcs.some(f => f.function_id === 404) && 'pump_speed' in p) {
          sPump = p.pump_speed;
        }

        result.push({
          step_no: stepCount++,
          treatment_origin: `${tr.position}. ${tr.treatment_name}`,
          treatment_category: tr.category,
          label: s.label || `Langkah ${tr.treatment_number}`,
          functions: funcs,
          summary_temp: sTemp,
          summary_time_min: sTime || 0,
          summary_water_l: sWater || 0,
          summary_pump_pct: sPump || 85
        });
      });
    });

    return result;
  }, [procedureTreatments]);

  // 10. Compute Estimated Totals
  const totals = useMemo(() => {
    let totalMinutes = 0;
    let totalWater = 0;

    flattenedSteps.forEach(st => {
      totalMinutes += (st.summary_time_min || 0);
      if (st.summary_water_l) {
        totalWater += st.summary_water_l;
      }
    });

    return {
      treatmentsCount: procedureTreatments.length,
      stepsCount: flattenedSteps.length,
      durationMin: Math.round(totalMinutes),
      durationHrs: (totalMinutes / 60).toFixed(1),
      waterLiters: Math.round(totalWater)
    };
  }, [procedureTreatments, flattenedSteps]);

  // 11. Compute Chart Data
  const chartData = useMemo(() => {
    let currTime = 0;
    let currTemp = 30; // Ambient water start
    const categories = ['0m'];
    const tempSeries = [currTemp];

    flattenedSteps.forEach((st) => {
      const dur = st.summary_time_min > 0 ? st.summary_time_min : 5;
      currTime += dur;

      if (st.summary_temp !== null && st.summary_temp !== undefined) {
        currTemp = st.summary_temp;
      }

      categories.push(`${Math.round(currTime)}m`);
      tempSeries.push(currTemp);
    });

    return {
      categories,
      series: [
        {
          name: 'Suhu Target (°C)',
          data: tempSeries
        }
      ]
    };
  }, [flattenedSteps]);

  // 12. Save Procedure
  const handleSaveProcedure = async () => {
    if (!programName.trim()) {
      showToast('Nama program wajib diisi!', 'error');
      return;
    }
    if (procedureTreatments.length === 0) {
      showToast('Procedure minimal harus memiliki 1 Treatment!', 'error');
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        program_no: parseInt(programNo, 10),
        program_name: programName.trim().toUpperCase(),
        machine_code: machineCode || 'C012',
        sub_programs: procedureTreatments.map(t => ({
          position: t.position,
          treatment_id: t.treatment_id,
          treatment_number: t.treatment_number,
          treatment_name: t.treatment_name,
          parameters: t.parameters || {},
          steps: t.steps || []
        })),
        steps: flattenedSteps
      };

      const res = await axios.post('/api/programs/', payload);
      showToast(res.data.message || `Procedure M_${String(programNo).padStart(4, '0')}.PRG berhasil disimpan!`);
      fetchProgramList();
    } catch (err) {
      console.error('Gagal menyimpan procedure:', err);
      showToast('Gagal menyimpan procedure ke server', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  // 13. Compile and Download .PRG Binary
  const handleCompileAndDownload = async () => {
    try {
      await handleSaveProcedure();
      const res = await axios.post(`/api/programs/compile/${programNo}`);
      const link = document.createElement('a');
      link.href = `/api/programs/download/${programNo}`;
      link.setAttribute('download', `M_${String(programNo).padStart(4, '0')}.PRG`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      showToast(`Kompilasi sukses! Biner M_${String(programNo).padStart(4, '0')}.PRG (${res.data.records} baris) siap diunduh.`);
    } catch (err) {
      console.error('Kompilasi gagal:', err);
      showToast('Gagal melakukan kompilasi biner .PRG', 'error');
    }
  };

  const activeTreatment = procedureTreatments[selectedPosition] || null;

  return (
    <div className="mx-auto max-w-7xl p-4 md:p-6 space-y-6">
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-5 py-3 rounded-lg shadow-xl text-white font-medium transition-all ${notification.type === 'error' ? 'bg-rose-600' : 'bg-emerald-600'
          }`}>
          {notification.type === 'error' ? <AlertCircle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white p-6 rounded-2xl shadow-lg border border-blue-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-500/20 text-blue-200 border border-blue-400/30">
              OrgaTEX EDX300 Architecture
            </span>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-200 border border-emerald-400/30">
              Modular Procedure & Treatment Model
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-3">
            <Layers className="w-8 h-8 text-blue-400" />
            Pembuat Program OrgaTEX (EDX300)
          </h1>
          <p className="text-sm text-slate-300 mt-1 max-w-3xl">
            Alur pembuatan program tekstil berbasis modul <strong>Treatment (Sub-Program)</strong> yang dirangkai menjadi <strong>Procedure (Master Program)</strong>. Parameter proses (suhu, waktu tahan, sirkulasi) diatur per modul tanpa perlu menulis instruksi mikro step-by-step secara manual.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {viewMode === 'EDITOR' ? (
            <>
              <button
                onClick={() => setViewMode('LIST')}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-sm font-medium transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Daftar Program
              </button>
              <button
                onClick={() => setShowLibraryModal(true)}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium shadow transition-colors"
              >
                <Plus className="w-4 h-4" />
                Tambah Treatment
              </button>
              <button
                onClick={handleSaveProcedure}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-md transition-all disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {isSaving ? 'Menyimpan...' : 'Simpan Procedure'}
              </button>
              <button
                onClick={() => handleTransferToFtp(programNo, machineCode)}
                disabled={isTransferringFtp}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold shadow-md transition-all disabled:opacity-50"
                title={`Tulis file biner M_${String(programNo).padStart(4, '0')}.PRG langsung ke FTP Mesin ${machineCode}`}
              >
                <Send className={`w-4 h-4 ${isTransferringFtp ? 'animate-spin' : ''}`} />
                <span>{isTransferringFtp ? 'Menulis FTP...' : `Tulis ke FTP (${machineCode})`}</span>
              </button>
              <button
                onClick={handleCompileAndDownload}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-md transition-all"
              >
                <Download className="w-4 h-4" />
                Compile .PRG
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleCreateNewProcedure}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-md transition-all"
              >
                <Plus className="w-4 h-4" />
                Buat Procedure Baru
              </button>
              <button
                onClick={() => setShowLibraryModal(true)}
                className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-sm font-medium transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                Library Treatment ({treatmentsLibrary.length})
              </button>
            </>
          )}
        </div>
      </div>

      {/* BILAH PILIHAN MESIN AKTIF & STATUS KONTROLER FTP */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 rounded-2xl border border-indigo-500/30 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-indigo-500/20 text-indigo-400 rounded-xl border border-indigo-500/30">
            <Cpu className="w-6 h-6" />
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

      {/* Comparison Explainer Pill */}
      <div className="bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/50 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs md:text-sm text-blue-900 dark:text-blue-200">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Perbandingan UX: </span>
            Halaman ini menerapkan <strong>Model OrgaTEX EDX300</strong> (Penyusunan modul proses tingkat tinggi). Untuk perancangan langsung <em>step-by-step low-level</em> per microcode SECOM 777, Anda dapat membuka menu <strong>Program (SECOM Studio)</strong> di bilah navigasi kiri.
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a
            href="/programs"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/60 dark:hover:bg-blue-900 text-blue-800 dark:text-blue-200 font-medium transition-colors"
          >
            Buka SECOM Studio
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* VIEW MODE: LIST OF MASTER PROGRAMS                                    */}
      {/* ===================================================================== */}
      {viewMode === 'LIST' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-white dark:bg-boxdark p-4 rounded-xl border border-stroke dark:border-strokedark shadow-sm">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder={`Cari program mesin ${activeMachine} atau nomor...`}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-stroke dark:border-strokedark bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Filter Lingkup Mesin */}
              <div className="flex items-center gap-1 bg-slate-100 dark:bg-meta-4 p-1 rounded-lg border border-stroke dark:border-strokedark">
                <button
                  onClick={() => setFilterMachineScope('ACTIVE')}
                  className={`px-3 py-1.5 text-xs font-bold rounded-md transition flex items-center gap-1.5 ${filterMachineScope === 'ACTIVE'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-300 hover:text-black dark:hover:text-white'
                    }`}
                >
                  <Cpu className="w-3.5 h-3.5" />
                  <span>Mesin {activeMachine} ({activeMachineProgramsCount})</span>
                </button>
                <button
                  onClick={() => setFilterMachineScope('ALL')}
                  className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${filterMachineScope === 'ALL'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-300 hover:text-black dark:hover:text-white'
                    }`}
                >
                  <span>Semua Mesin ({programList.length})</span>
                </button>
              </div>

              <button
                onClick={fetchProgramList}
                className="p-2 rounded-lg border border-stroke dark:border-strokedark hover:bg-slate-100 dark:hover:bg-meta-4 transition-colors"
                title="Muat Ulang"
              >
                <RefreshCw className="w-4 h-4 text-slate-600 dark:text-slate-300" />
              </button>
            </div>
          </div>

          {/* Table / Grid */}
          <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-stroke dark:border-strokedark bg-slate-50 dark:bg-meta-4 text-slate-600 dark:text-slate-300 font-semibold">
                    <th className="p-4 w-24">No. Program</th>
                    <th className="p-4 w-28">Mesin</th>
                    <th className="p-4">Nama Prosedur (Master Program)</th>
                    <th className="p-4">Struktur Modul</th>
                    <th className="p-4">Total Langkah PRG</th>
                    <th className="p-4">Tipe Berkas</th>
                    <th className="p-4 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stroke dark:divide-strokedark">
                  {loadingList ? (
                    <tr>
                      <td colSpan="7" className="p-8 text-center text-slate-500">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                        Memuat daftar program OrgaTEX...
                      </td>
                    </tr>
                  ) : programList
                    .filter(p => {
                      const matchSearch = String(p.program_number).includes(searchTerm) ||
                        (p.program_name && p.program_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
                        (p.machine_code && p.machine_code.toLowerCase().includes(searchTerm.toLowerCase()));
                      const pMach = (p.machine_code || 'TD12').toUpperCase();
                      if (filterMachineScope === 'ACTIVE' && pMach !== activeMachine.toUpperCase()) {
                        return false;
                      }
                      return matchSearch;
                    }).length === 0 ? (
                    <tr>
                      <td colSpan="7" className="p-8 text-center text-slate-500">
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
                    programList
                      .filter(p => {
                        const matchSearch = String(p.program_number).includes(searchTerm) ||
                          (p.program_name && p.program_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
                          (p.machine_code && p.machine_code.toLowerCase().includes(searchTerm.toLowerCase()));
                        const pMach = (p.machine_code || 'TD12').toUpperCase();
                        if (filterMachineScope === 'ACTIVE' && pMach !== activeMachine.toUpperCase()) {
                          return false;
                        }
                        return matchSearch;
                      })
                      .map((p) => (
                        <tr key={p.program_number} className="hover:bg-slate-50/80 dark:hover:bg-meta-4/40 transition-colors">
                          <td className="p-4 font-mono font-bold text-blue-600 dark:text-blue-400">
                            M_{String(p.program_number).padStart(4, '0')}
                          </td>
                          <td className="p-4">
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded font-mono text-xs font-bold bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-500/20">
                              <Cpu className="w-3 h-3 text-blue-500" />
                              {p.machine_code || 'TD12'}
                            </span>
                          </td>
                          <td className="p-4">
                            <div className="font-semibold text-slate-900 dark:text-white">
                              {p.program_name}
                            </div>
                            <div className="text-xs text-slate-500">
                              Target Mesin: {p.machine_code || activeMachine} ({availableMachines.find(m => m.machine_no === (p.machine_code || activeMachine))?.display_name || 'Jet Dyeing'})
                            </div>
                          </td>
                          <td className="p-4">
                            <div className="flex flex-wrap gap-1">
                              <span className="px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                                Pretreatment
                              </span>
                              <span className="px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300">
                                Dyeing
                              </span>
                              <span className="px-2 py-0.5 text-xs rounded bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                                Soaping
                              </span>
                              <span className="px-2 py-0.5 text-xs rounded bg-cyan-100 text-cyan-800 dark:bg-cyan-950/60 dark:text-cyan-300">
                                Rinse
                              </span>
                            </div>
                          </td>
                          <td className="p-4 font-medium">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-semibold">
                              <FileCode className="w-3.5 h-3.5 text-slate-500" />
                              {p.total_steps || 0} Langkah Mikro
                            </span>
                          </td>
                          <td className="p-4">
                            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                              .PRG (65B Biner)
                            </span>
                          </td>
                          <td className="p-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => setFtpTransferModal(p)}
                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition-colors"
                                title={`Tulis biner M_${String(p.program_number).padStart(4, '0')}.PRG langsung ke FTP Mesin ${p.machine_code || activeMachine}`}
                              >
                                <Send className="w-3.5 h-3.5" />
                                <span>Tulis FTP</span>
                              </button>
                              <button
                                onClick={() => handleOpenProgram(p.program_number)}
                                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-sm transition-colors"
                              >
                                Buka di EDX300
                                <ChevronRight className="w-3.5 h-3.5" />
                              </button>
                              <a
                                href={`/api/programs/download/${p.program_number}`}
                                download={`M_${String(p.program_number).padStart(4, '0')}.PRG`}
                                className="p-1.5 rounded-lg border border-stroke dark:border-strokedark hover:bg-slate-100 dark:hover:bg-meta-4 text-slate-600 dark:text-slate-300 transition-colors"
                                title="Unduh Biner .PRG"
                              >
                                <Download className="w-4 h-4" />
                              </a>
                            </div>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* MODAL KONFIRMASI TRANSFER KE FTP KONTROLER */}
          {ftpTransferModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
              <div className="bg-white dark:bg-boxdark rounded-2xl border border-stroke dark:border-strokedark shadow-2xl max-w-md w-full p-6 space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-indigo-500/10 text-indigo-600 rounded-lg">
                      <Send className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-black dark:text-white">
                        Tulis Program ke FTP Kontroler
                      </h3>
                      <p className="text-[11px] text-gray-500">Kirim file biner .PRG langsung ke SETEX 777</p>
                    </div>
                  </div>
                  <button onClick={() => setFtpTransferModal(null)} className="text-gray-400 hover:text-gray-600">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="bg-gray-50 dark:bg-meta-4/40 p-4 rounded-xl border border-stroke dark:border-strokedark space-y-2.5 text-xs">
                  <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                    <span className="text-gray-500 font-medium">Program Target:</span>
                    <strong className="text-black dark:text-white font-mono">
                      M_{String(ftpTransferModal.program_number).padStart(4, '0')}.PRG ({ftpTransferModal.program_name})
                    </strong>
                  </div>
                  <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                    <span className="text-gray-500 font-medium">Mesin Target:</span>
                    <span className="font-bold text-blue-600 font-mono">
                      Mesin {ftpTransferModal.machine_code || activeMachine}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pb-2 border-b border-stroke dark:border-strokedark">
                    <span className="text-gray-500 font-medium">IP Controller:</span>
                    <span className="font-mono font-bold text-emerald-600">
                      {availableMachines.find(m => m.machine_no === (ftpTransferModal.machine_code || activeMachine))?.ip_address || '172.16.110.101'}:21
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 font-medium">Direktori Remote:</span>
                    <span className="font-mono text-gray-700 dark:text-gray-300">
                      /Storage/sc777ce/Programs/
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-gray-500">
                  File biner M_{String(ftpTransferModal.program_number).padStart(4, '0')}.PRG akan langsung disimpan ke storage kontroler mesin ini dan siap dijalankan oleh operator pada HMI SETEX 777.
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
                    <Send className={`w-4 h-4 ${isTransferringFtp ? 'animate-spin' : ''}`} />
                    <span>{isTransferringFtp ? 'Sedang Mentransfer...' : `Tulis Sekarang ke FTP Mesin ${ftpTransferModal.machine_code || activeMachine}`}</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW MODE: PROCEDURE & TREATMENT EDITOR                               */}
      {/* ===================================================================== */}
      {viewMode === 'EDITOR' && (
        <div className="space-y-6">
          {/* Metadata & Quick Actions Bar */}
          <div className="bg-white dark:bg-boxdark p-5 rounded-2xl border border-stroke dark:border-strokedark shadow-sm">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              {/* Program No */}
              <div className="md:col-span-2">
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 uppercase tracking-wider">
                  No. Program
                </label>
                <div className="flex items-center">
                  <span className="px-3 py-2 bg-slate-100 dark:bg-meta-4 text-slate-600 dark:text-slate-300 font-mono font-bold rounded-l-lg border border-r-0 border-stroke dark:border-strokedark text-sm">
                    M_
                  </span>
                  <input
                    type="number"
                    value={programNo}
                    onChange={(e) => setProgramNo(parseInt(e.target.value, 10) || 1)}
                    className="w-full px-3 py-2 text-sm font-mono font-bold rounded-r-lg border border-stroke dark:border-strokedark bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Procedure Name */}
              <div className="md:col-span-4">
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 uppercase tracking-wider">
                  Nama Prosedur (Master Procedure)
                </label>
                <input
                  type="text"
                  value={programName}
                  onChange={(e) => setProgramName(e.target.value.toUpperCase())}
                  placeholder="Contoh: COTTON REACTIVE DARK 60C"
                  className="w-full px-3 py-2 text-sm font-bold uppercase rounded-lg border border-stroke dark:border-strokedark bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Target Machine */}
              <div className="md:col-span-3">
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-blue-500" />
                  <span>Target Mesin & Kontroler:</span>
                </label>
                <select
                  value={machineCode}
                  onChange={(e) => setMachineCode(e.target.value)}
                  className="w-full px-3 py-2 text-sm font-bold font-mono rounded-lg border border-stroke dark:border-strokedark bg-transparent text-primary dark:text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                >
                  {availableMachines.map((m) => (
                    <option key={m.machine_no} value={m.machine_no} className="bg-white dark:bg-boxdark text-black dark:text-white">
                      Mesin {m.machine_no} ({m.ip_address})
                    </option>
                  ))}
                </select>
              </div>

              {/* Summary Badges */}
              <div className="md:col-span-3 flex items-center justify-end gap-3 pt-2 md:pt-0">
                <div className="text-right">
                  <div className="text-xs text-slate-500">Estimasi Siklus:</div>
                  <div className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-1 justify-end">
                    <Clock className="w-4 h-4 text-blue-500" />
                    {totals.durationMin}m ({totals.durationHrs} jam)
                  </div>
                </div>
                <div className="h-8 w-px bg-stroke dark:bg-strokedark" />
                <div className="text-right">
                  <div className="text-xs text-slate-500">Kompilasi SECOM:</div>
                  <button
                    onClick={() => setShowFlattenedModal(true)}
                    className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 justify-end"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    {totals.stepsCount} Langkah PRG
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Main 2-Column Modular Workspace */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* =============================================================== */}
            {/* COLUMN 1: PROCEDURE SEQUENCER (TREATMENTS LIST)                 */}
            {/* =============================================================== */}
            <div className="lg:col-span-5 space-y-4">
              <div className="bg-white dark:bg-boxdark p-5 rounded-2xl border border-stroke dark:border-strokedark shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-stroke dark:border-strokedark mb-4">
                  <div>
                    <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <Boxes className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      Urutan Treatment (Level 1)
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Rangkaian modul proses yang akan dieksekusi mesin
                    </p>
                  </div>
                  <button
                    onClick={() => setShowLibraryModal(true)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Tambah
                  </button>
                </div>

                {procedureTreatments.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 border-2 border-dashed border-stroke dark:border-strokedark rounded-xl">
                    <p className="text-sm font-medium">Belum ada treatment dalam procedure ini.</p>
                    <button
                      onClick={() => setShowLibraryModal(true)}
                      className="mt-3 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500"
                    >
                      Pilih dari Library
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {procedureTreatments.map((tr, idx) => {
                      const isSelected = idx === selectedPosition;
                      const catClass = CATEGORY_COLORS[tr.category] || CATEGORY_COLORS.General;
                      const p = tr.parameters || {};

                      return (
                        <div
                          key={`${tr.treatment_number}-${idx}`}
                          onClick={() => setSelectedPosition(idx)}
                          className={`p-3.5 rounded-xl border transition-all cursor-pointer relative ${isSelected
                            ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/40 shadow-sm ring-1 ring-blue-500'
                            : 'border-stroke dark:border-strokedark bg-slate-50/50 dark:bg-meta-4/30 hover:bg-slate-100/80 dark:hover:bg-meta-4/60'
                            }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <span className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono text-xs font-bold flex items-center justify-center shrink-0">
                                {idx + 1}
                              </span>
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-sm text-slate-900 dark:text-white truncate">
                                    {tr.treatment_name}
                                  </span>
                                  <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border shrink-0 ${catClass}`}>
                                    {tr.category || 'Process'}
                                  </span>
                                </div>
                                <div className="text-xs text-slate-500 font-mono">
                                  Kode: {tr.treatment_number}
                                </div>
                              </div>
                            </div>

                            {/* Position Reordering / Delete Actions */}
                            <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                              <button
                                onClick={() => handleMoveTreatment(idx, 'UP')}
                                disabled={idx === 0}
                                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 disabled:opacity-30"
                                title="Pindah ke Atas"
                              >
                                <ArrowUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleMoveTreatment(idx, 'DOWN')}
                                disabled={idx === procedureTreatments.length - 1}
                                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 disabled:opacity-30"
                                title="Pindah ke Bawah"
                              >
                                <ArrowDown className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleRemoveTreatment(idx)}
                                className="p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950 text-rose-500"
                                title="Hapus Modul Ini"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          {/* Quick Parameter Summary Chips */}
                          <div className="mt-2.5 pt-2 border-t border-slate-200/60 dark:border-slate-700/60 flex flex-wrap gap-2 text-[11px] text-slate-600 dark:text-slate-300 font-mono">
                            {p.temperature && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                                <Flame className="w-3 h-3 text-red-500" />
                                {p.temperature}°C
                              </span>
                            )}
                            {p.hold_time && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                                <Clock className="w-3 h-3 text-orange-500" />
                                {p.hold_time}m
                              </span>
                            )}
                            {p.water_level && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                                <Droplet className="w-3 h-3 text-blue-500" />
                                {p.water_level}L
                              </span>
                            )}
                            {p.pump_speed && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                                <Gauge className="w-3 h-3 text-amber-500" />
                                {p.pump_speed}%
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* =============================================================== */}
            {/* COLUMN 2: ACTIVE TREATMENT PARAMETERS & STEPS PREVIEW           */}
            {/* =============================================================== */}
            <div className="lg:col-span-7 space-y-4">
              {activeTreatment ? (
                <div className="bg-white dark:bg-boxdark p-5 rounded-2xl border border-stroke dark:border-strokedark shadow-sm space-y-6">
                  {/* Treatment Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-stroke dark:border-strokedark">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          Posisi #{selectedPosition + 1}
                        </span>
                        <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300">
                          {activeTreatment.treatment_number}
                        </span>
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${CATEGORY_COLORS[activeTreatment.category] || CATEGORY_COLORS.General}`}>
                          {activeTreatment.category || 'General'}
                        </span>
                      </div>
                      <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                        {activeTreatment.treatment_name}
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {activeTreatment.comment || 'Modul perlakuan terverifikasi OrgaTEX'}
                      </p>
                    </div>

                    <div className="text-right">
                      <span className="text-xs text-slate-500 block">Kompilasi Biner:</span>
                      <span className="text-xs font-bold font-mono px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300">
                        {activeTreatment.steps ? activeTreatment.steps.length : 0} Langkah Mikro
                      </span>
                    </div>
                  </div>

                  {/* Section: Treatment Parameter Overrides (EDX300 Core Innovation) */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <Sliders className="w-4 h-4 text-blue-600" />
                        Parameter Proses Modul (Treatment Parameters)
                      </h4>
                      <span className="text-[11px] text-slate-400 italic">
                        Perubahan otomatis mengupdate instruksi mikro SECOM
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {/* Temperature */}
                      <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-slate-50/50 dark:bg-meta-4/20 space-y-2">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <Flame className="w-4 h-4 text-red-500" />
                            Suhu Target (°C)
                          </span>
                          <span className="font-mono text-red-600 dark:text-red-400 font-bold">
                            {activeTreatment.parameters?.temperature ?? 0} °C
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min="20"
                            max="140"
                            step="1"
                            value={activeTreatment.parameters?.temperature ?? 20}
                            onChange={(e) => handleUpdateParameter('temperature', e.target.value)}
                            className="w-full accent-red-600"
                          />
                          <input
                            type="number"
                            min="20"
                            max="140"
                            value={activeTreatment.parameters?.temperature ?? 20}
                            onChange={(e) => handleUpdateParameter('temperature', e.target.value)}
                            className="w-16 px-2 py-1 text-xs font-mono font-bold rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-right"
                          />
                        </div>
                      </div>

                      {/* Hold Time */}
                      <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-slate-50/50 dark:bg-meta-4/20 space-y-2">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <Clock className="w-4 h-4 text-orange-500" />
                            Waktu Tahan / Hold (Menit)
                          </span>
                          <span className="font-mono text-orange-600 dark:text-orange-400 font-bold">
                            {activeTreatment.parameters?.hold_time ?? 0} m
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min="1"
                            max="180"
                            step="1"
                            value={activeTreatment.parameters?.hold_time ?? 15}
                            onChange={(e) => handleUpdateParameter('hold_time', e.target.value)}
                            className="w-full accent-orange-600"
                          />
                          <input
                            type="number"
                            min="1"
                            max="180"
                            value={activeTreatment.parameters?.hold_time ?? 15}
                            onChange={(e) => handleUpdateParameter('hold_time', e.target.value)}
                            className="w-16 px-2 py-1 text-xs font-mono font-bold rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-right"
                          />
                        </div>
                      </div>

                      {/* Water Level / Volume */}
                      <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-slate-50/50 dark:bg-meta-4/20 space-y-2">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <Droplet className="w-4 h-4 text-blue-500" />
                            Level Air (Liter)
                          </span>
                          <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">
                            {activeTreatment.parameters?.water_level ?? 0} L
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min="500"
                            max="6000"
                            step="100"
                            value={activeTreatment.parameters?.water_level ?? 2500}
                            onChange={(e) => handleUpdateParameter('water_level', e.target.value)}
                            className="w-full accent-blue-600"
                          />
                          <input
                            type="number"
                            min="500"
                            max="6000"
                            step="50"
                            value={activeTreatment.parameters?.water_level ?? 2500}
                            onChange={(e) => handleUpdateParameter('water_level', e.target.value)}
                            className="w-20 px-2 py-1 text-xs font-mono font-bold rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-right"
                          />
                        </div>
                      </div>

                      {/* Pump Speed */}
                      <div className="p-3.5 rounded-xl border border-stroke dark:border-strokedark bg-slate-50/50 dark:bg-meta-4/20 space-y-2">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <Gauge className="w-4 h-4 text-amber-500" />
                            Kecepatan Pompa (%)
                          </span>
                          <span className="font-mono text-amber-600 dark:text-amber-400 font-bold">
                            {activeTreatment.parameters?.pump_speed ?? 0} %
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min="30"
                            max="100"
                            step="5"
                            value={activeTreatment.parameters?.pump_speed ?? 85}
                            onChange={(e) => handleUpdateParameter('pump_speed', e.target.value)}
                            className="w-full accent-amber-600"
                          />
                          <input
                            type="number"
                            min="30"
                            max="100"
                            value={activeTreatment.parameters?.pump_speed ?? 85}
                            onChange={(e) => handleUpdateParameter('pump_speed', e.target.value)}
                            className="w-16 px-2 py-1 text-xs font-mono font-bold rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-right"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Section: Internal Steps Preview */}
                  <div className="space-y-3 pt-3 border-t border-stroke dark:border-strokedark">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <FileCode className="w-4 h-4 text-indigo-500" />
                        Langkah Internal Mikrokontroler ({activeTreatment.steps ? activeTreatment.steps.length : 0} Steps)
                      </span>
                      <span className="text-xs text-slate-400 font-normal">
                        Dihasilkan secara otomatis oleh modul OrgaTEX
                      </span>
                    </h4>

                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                      {(activeTreatment.steps || []).map((st, sIdx) => (
                        <div
                          key={sIdx}
                          className="p-3 rounded-lg border border-stroke dark:border-strokedark bg-slate-50 dark:bg-meta-4/40 flex items-center justify-between text-xs"
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="w-5 h-5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono font-bold flex items-center justify-center text-[10px]">
                              {st.step_no}
                            </span>
                            <div>
                              <div className="font-semibold text-slate-800 dark:text-slate-200">
                                {st.label}
                              </div>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {(st.functions || []).map((f, fIdx) => (
                                  <span
                                    key={fIdx}
                                    className="px-1.5 py-0.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark font-mono text-[10px] text-slate-600 dark:text-slate-300"
                                  >
                                    F{f.function_id}: {f.name}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="text-right font-mono text-[11px] text-slate-500">
                            {st.summary_temp ? `${st.summary_temp}°C` : ''}
                            {st.summary_time_min ? ` • ${st.summary_time_min}m` : ''}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white dark:bg-boxdark p-12 rounded-2xl border border-stroke dark:border-strokedark text-center text-slate-400">
                  <p>Pilih Treatment di sebelah kiri untuk melihat dan mengubah parameter proses.</p>
                </div>
              )}
            </div>
          </div>

          {/* Real-time Dynamic Temperature Curve */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2 text-base">
                <Flame className="w-5 h-5 text-red-500" />
                Kurva Profil Suhu Siklus Utuh (°C)
              </h3>
              <button
                onClick={() => setShowCurveChart(!showCurveChart)}
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
              >
                {showCurveChart ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                {showCurveChart ? 'Sembunyikan Grafik' : 'Tampilkan Grafik'}
              </button>
            </div>

            {showCurveChart && (
              <TempCurveChart
                series={chartData.series}
                categories={chartData.categories}
                title={`Profil Kurva Suhu OrgaTEX EDX300: ${programName} (Total: ${totals.durationMin} Menit)`}
              />
            )}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: TREATMENT LIBRARY CATALOG                                      */}
      {/* ===================================================================== */}
      {showLibraryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-boxdark rounded-2xl shadow-2xl border border-stroke dark:border-strokedark max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-fadeIn">
            {/* Header */}
            <div className="p-5 border-b border-stroke dark:border-strokedark flex items-center justify-between bg-slate-50 dark:bg-meta-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-indigo-600" />
                  Katalog Treatment OrgaTEX (Sub-Programs Level 2)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Pilih modul proses standar tekstil untuk disisipkan ke dalam Master Procedure
                </p>
              </div>
              <button
                onClick={() => setShowLibraryModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700"
              >
                ✕
              </button>
            </div>

            {/* Filter Categories */}
            <div className="p-4 border-b border-stroke dark:border-strokedark flex flex-wrap gap-2 bg-slate-50/50 dark:bg-meta-4/20">
              {['ALL', 'Pretreatment', 'Dyeing', 'Washing', 'Neutralization', 'Rinse', 'Finishing', 'End'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setTreatmentFilterCategory(cat)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${treatmentFilterCategory === cat
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-meta-4'
                    }`}
                >
                  {cat === 'ALL' ? 'Semua Kategori' : cat}
                </button>
              ))}
            </div>

            {/* Treatment Cards Grid */}
            <div className="p-5 overflow-y-auto space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {treatmentsLibrary
                  .filter(t => treatmentFilterCategory === 'ALL' || t.category === treatmentFilterCategory)
                  .map((t) => {
                    const catClass = CATEGORY_COLORS[t.category] || CATEGORY_COLORS.General;
                    const p = t.parameters || {};

                    return (
                      <div
                        key={t.id || t.number}
                        className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-blue-400 hover:shadow-md transition-all flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              {t.number}
                            </span>
                            <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${catClass}`}>
                              {t.category || 'General'}
                            </span>
                          </div>

                          <h4 className="font-bold text-slate-900 dark:text-white text-sm mb-1">
                            {t.name}
                          </h4>
                          <p className="text-xs text-slate-500 mb-3 line-clamp-2">
                            {t.comment || 'Modul proses pencelupan standar.'}
                          </p>

                          {/* Quick Parameters */}
                          <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-600 dark:text-slate-400 mb-4">
                            {p.temperature && (
                              <span className="flex items-center gap-1">
                                <Flame className="w-3 h-3 text-red-500" />
                                {p.temperature}°C
                              </span>
                            )}
                            {p.hold_time && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3 text-orange-500" />
                                {p.hold_time}m
                              </span>
                            )}
                            {p.water_level && (
                              <span className="flex items-center gap-1">
                                <Droplet className="w-3 h-3 text-blue-500" />
                                {p.water_level}L
                              </span>
                            )}
                            <span className="text-slate-400">
                              • {t.steps ? t.steps.length : 0} langkah PRG
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={() => handleAddTreatmentToProcedure(t)}
                          className="w-full py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                        >
                          <Plus className="w-4 h-4" />
                          Sisipkan Modul Ini
                        </button>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: FLATTENED SECOM 777 STEPS INSPECTOR                            */}
      {/* ===================================================================== */}
      {showFlattenedModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-boxdark rounded-2xl shadow-2xl border border-stroke dark:border-strokedark max-w-5xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-fadeIn">
            {/* Header */}
            <div className="p-5 border-b border-stroke dark:border-strokedark flex items-center justify-between bg-slate-50 dark:bg-meta-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <FileCode className="w-5 h-5 text-emerald-600" />
                  Kompilasi Biner Mikro SECOM 777 ({flattenedSteps.length} Baris Record)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Hasil penggabungan modul Treatment menjadi baris perintah biner mikrokontroler 65-byte (M_{String(programNo).padStart(4, '0')}.PRG)
                </p>
              </div>
              <button
                onClick={() => setShowFlattenedModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700"
              >
                ✕
              </button>
            </div>

            {/* Steps Table */}
            <div className="p-5 overflow-y-auto">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-stroke dark:border-strokedark bg-slate-50 dark:bg-meta-4 font-semibold text-slate-600 dark:text-slate-300">
                      <th className="p-3 w-16">Step #</th>
                      <th className="p-3">Asal Treatment</th>
                      <th className="p-3">Deskripsi Langkah</th>
                      <th className="p-3">Fungsi Mikro (F-Code & Parameter)</th>
                      <th className="p-3 text-right">Suhu Target</th>
                      <th className="p-3 text-right">Durasi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stroke dark:divide-strokedark font-mono">
                    {flattenedSteps.map((st) => (
                      <tr key={st.step_no} className="hover:bg-slate-50/80 dark:hover:bg-meta-4/30">
                        <td className="p-3 font-bold text-blue-600 dark:text-blue-400">
                          #{st.step_no}
                        </td>
                        <td className="p-3 font-sans">
                          <span className="font-semibold text-slate-800 dark:text-slate-200">
                            {st.treatment_origin}
                          </span>
                        </td>
                        <td className="p-3 font-sans text-slate-700 dark:text-slate-300">
                          {st.label}
                        </td>
                        <td className="p-3">
                          <div className="flex flex-wrap gap-1">
                            {st.functions.map((fn, fIdx) => (
                              <span
                                key={fIdx}
                                className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] border border-stroke dark:border-strokedark"
                              >
                                <strong>F{fn.function_id}</strong>: {fn.name} ({fn.params.join(', ')})
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="p-3 text-right text-red-600 dark:text-red-400 font-bold">
                          {st.summary_temp ? `${st.summary_temp}°C` : '-'}
                        </td>
                        <td className="p-3 text-right text-orange-600 dark:text-orange-400 font-bold">
                          {st.summary_time_min ? `${st.summary_time_min}m` : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-stroke dark:border-strokedark bg-slate-50 dark:bg-meta-4 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Format: 384-byte Header + {flattenedSteps.length} × 65-byte Steps
              </span>
              <button
                onClick={handleCompileAndDownload}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow transition-colors"
              >
                <Download className="w-4 h-4" />
                Unduh Biner .PRG Sekarang
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
