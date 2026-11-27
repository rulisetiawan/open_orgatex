import React, { useState, useEffect, useMemo } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { 
  Plus, 
  Download, 
  Send,
  RefreshCw, 
  Trash2, 
  X, 
  Cpu, 
  Sparkles, 
  Lock,
  ArrowLeft,
  Search,
  MoveRight
} from 'lucide-react';
import axios from 'axios';
import { useToast } from '../../context/ToastContext';

const API_BASE = '/api/planning';

const STATUS_CONFIG = {
  PLANNING: { label: 'PLAN', color: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30' },
  QUEUED: { label: 'Q', color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30' },
  WAITING_LA: { label: 'LA', color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30' },
  RUNNING: { label: 'RUN', color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30' },
  COMPLETED: { label: 'DONE', color: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/30' },
};

const KanbanView = () => {
  const { toast, confirm } = useToast();
  const [compactDensity, setCompactDensity] = useState(false);
  const [batches, setBatches] = useState([]);
  const [machineList, setMachineList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  
  // Search & Filter state
  const [planningSearch, setPlanningSearch] = useState('');
  const [machineSearch, setMachineSearch] = useState('');
  const [machineFilterType, setMachineFilterType] = useState('KEY_MACHINES');
  const [selectedGroup, setSelectedGroup] = useState('SEMUA');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [availablePrograms, setAvailablePrograms] = useState([
    { no: 401, name: 'M_0401.PRG - Reactive Dyeing Standard' },
    { no: 182, name: 'M_0182.PRG - Cotton Scouring & Bleach' },
    { no: 502, name: 'M_0502.PRG - Disperse Poly Jet 130C' },
    { no: 1, name: 'M_0001.PRG - Quick Rinsing & Neutral' },
  ]);

  // Form State
  const [form, setForm] = useState({
    batch_no: '',
    reference_no: '',
    machine_no: 'DA01',
    program_no: 1,
    recipe_name: 'Reactive Dyeing Standard Formula',
    customer: 'PT. SMM JETFLOW',
    article: 'CM 30S RIB 100% Cotton',
    color_code: '1650159',
    color_name: 'UNGU TUA',
    fabric_weight_kg: 350.0,
    liquor_ratio: 8.0,
    status: 'PLANNING'
  });

  // FTP Dispatch Batch Modal State
  const [ftpDispatchModalOpen, setFtpDispatchModalOpen] = useState(false);
  const [batchToDispatch, setBatchToDispatch] = useState(null);
  const [dispatchIp, setDispatchIp] = useState('192.168.1.95');
  const [dispatchModel, setDispatchModel] = useState('network_ot');
  const [isDispatching, setIsDispatching] = useState(false);
  const [isBulkSending, setIsBulkSending] = useState(false);

  // Bulk Send Antrean to HMI Controller (Khusus Mesin DA01 / M_95)
  const handleBulkSendToHmi = async (machNo = 'DA01') => {
    if (machNo !== 'DA01' && machNo !== 'M_95') {
      toast.warning(`Pengiriman massal (bulk) ke HMI hanya diizinkan untuk Mesin DA01/M_95. Mesin ${machNo} dalam mode read-only.`, {
        title: 'Peringatan Keamanan',
      });
      return;
    }

    const queuedBatches = batches.filter(
      b => b.machine_no === machNo && (b.status === 'QUEUED' || b.status === 'WAITING_LA' || b.status === 'RUNNING')
    );

    if (queuedBatches.length === 0) {
      toast.info(`Tidak ada batch antrean aktif untuk mesin ${machNo}.`);
      return;
    }

    const confirmMsg = `Sistem akan mengompilasi ${queuedBatches.length} batch antrean ke berkas QUEUE.BTD dan mengunggahnya ke kontroler HMI mesin ${machNo}.\n\nApakah Anda yakin ingin mereplace antrean di HMI ${machNo} sekarang?`;

    const ok = await confirm(confirmMsg, {
      title: `Kirim Bulk ke HMI ${machNo}`,
      confirmText: 'Ya, Kirim Antrean',
    });
    if (!ok) return;

    setIsBulkSending(true);
    try {
      const res = await axios.post('/api/ftp/bulk-replace-queue', {
        machine_no: machNo,
        ip: '192.168.1.95',
        port: 21
      });
      toast.success(res.data.message || `Berhasil mengirim ${queuedBatches.length} batch antrean ke HMI ${machNo}!`);
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      toast.error(`Gagal mengirim antrean ke HMI ${machNo}: ` + msg);
    } finally {
      setIsBulkSending(false);
    }
  };

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/`);
      setBatches(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil data batch:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPrograms = async () => {
    try {
      const res = await axios.get('/api/programs/');
      if (res.data && res.data.length > 0) {
        setAvailablePrograms(res.data.map(p => {
          const pNo = p.program_number || p.program_no;
          const pName = p.program_name || p.name || 'Program';
          return {
            no: pNo,
            name: `M_${String(pNo).padStart(4, '0')}.PRG - ${pName}`,
            rawName: pName,
            mach: p.machine_code
          };
        }));
      }
    } catch (err) {
      // Keep defaults
    }
  };

  const fetchMachines = async () => {
    try {
      const res = await axios.get('/api/machines');
      if (res.data && Array.isArray(res.data) && res.data.length > 0) {
        setMachineList(res.data);
      } else {
        setMachineList([
          { machine_no: 'DA01', display_name: 'SETEX 797CE Mesin DA01', group_name: 'Dyeing Section A', controller_type: 'SETEX 797CE', ip_address: '192.168.1.95', status: 'ONLINE' },
          { machine_no: 'M_95', display_name: 'SETEX 797CE Mesin DA01 (M_95)', group_name: 'Dyeing Section A', controller_type: 'SETEX 797CE', ip_address: '192.168.1.95', status: 'ONLINE' },
          { machine_no: '1A', display_name: 'Mesin 1A', group_name: 'Section A', controller_type: 'SECOM 777', ip_address: '172.16.110.101', status: 'ONLINE' },
          { machine_no: '2A', display_name: 'Mesin 2A', group_name: 'Section A', controller_type: 'SECOM 777', ip_address: '172.16.110.102', status: 'ONLINE' },
          { machine_no: '3A', display_name: 'Mesin 3A', group_name: 'Section A', controller_type: 'SECOM 777', ip_address: '172.16.110.103', status: 'ONLINE' },
          { machine_no: '1B', display_name: 'Mesin 1B', group_name: 'Section B', controller_type: 'SECOM 777', ip_address: '172.16.110.104', status: 'ONLINE' },
          { machine_no: '2B', display_name: 'Mesin 2B', group_name: 'Section B', controller_type: 'SECOM 777', ip_address: '172.16.110.105', status: 'ONLINE' },
        ]);
      }
    } catch (err) {
      console.error('Gagal mengambil data mesin:', err);
    }
  };

  useEffect(() => {
    fetchBatches();
    fetchPrograms();
    fetchMachines();
  }, []);

  const handleSyncDB = async () => {
    setSyncing(true);
    try {
      const res = await axios.post('/api/database/sync');
      toast.success(res.data.message || 'Sinkronisasi PostgreSQL & SQLite selesai!');
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      toast.error('Gagal sinkronisasi DB: ' + msg);
    } finally {
      setSyncing(false);
    }
  };

  const planningBatches = useMemo(() => {
    let list = batches.filter(b => (b.status || '').toUpperCase() === 'PLANNING');
    if (planningSearch.trim()) {
      const q = planningSearch.toLowerCase();
      list = list.filter(b => 
        (b.batch_no || '').toLowerCase().includes(q) ||
        (b.reference_no || '').toLowerCase().includes(q) ||
        (b.recipe_name || '').toLowerCase().includes(q) ||
        (b.customer || '').toLowerCase().includes(q) ||
        (b.article || '').toLowerCase().includes(q) ||
        (b.color_name || '').toLowerCase().includes(q)
      );
    }
    return list.sort((a, b) => (a.position || 0) - (b.position || 0));
  }, [batches, planningSearch]);

  const batchesByMachine = useMemo(() => {
    const map = {};
    batches.forEach(b => {
      const st = (b.status || '').toUpperCase();
      if (st !== 'PLANNING') {
        const m = (b.machine_no || 'DA01').toUpperCase();
        if (!map[m]) map[m] = [];
        map[m].push(b);
      }
    });
    Object.keys(map).forEach(m => {
      map[m].sort((a, b) => (a.position || 0) - (b.position || 0));
    });
    return map;
  }, [batches]);

  const { availableGroups, groupCounts } = useMemo(() => {
    const counts = {};
    machineList.forEach(m => {
      const g = (m.group_name || '').trim();
      if (g) {
        counts[g] = (counts[g] || 0) + 1;
      }
    });
    const sortedGroups = Object.keys(counts).sort((a, b) => a.localeCompare(b));
    return {
      availableGroups: ['SEMUA', ...sortedGroups],
      groupCounts: counts,
    };
  }, [machineList]);

  const handleSelectGroup = (groupVal) => {
    setSelectedGroup(groupVal);
    if (groupVal !== 'SEMUA' && machineFilterType === 'KEY_MACHINES') {
      setMachineFilterType('ALL');
    }
  };

  const displayedMachines = useMemo(() => {
    let list = [...machineList];

    list.sort((a, b) => {
      const isAKey = a.machine_no === 'DA01' || a.machine_no === 'M_95';
      const isBKey = b.machine_no === 'DA01' || b.machine_no === 'M_95';
      if (isAKey && !isBKey) return -1;
      if (!isAKey && isBKey) return 1;
      return a.machine_no.localeCompare(b.machine_no);
    });

    if (machineFilterType === 'KEY_MACHINES') {
      list = list.filter(m => m.machine_no === 'DA01' || m.machine_no === 'M_95');
    } else if (machineFilterType === 'WITH_QUEUES') {
      list = list.filter(m => (batchesByMachine[m.machine_no.toUpperCase()] || []).length > 0);
    }

    if (selectedGroup !== 'SEMUA') {
      list = list.filter(m => m.group_name === selectedGroup);
    }

    if (machineSearch.trim()) {
      const q = machineSearch.toLowerCase();
      list = list.filter(m => 
        m.machine_no.toLowerCase().includes(q) || 
        (m.display_name || '').toLowerCase().includes(q) ||
        (m.ip_address || '').toLowerCase().includes(q)
      );
    }

    return list;
  }, [machineList, machineFilterType, selectedGroup, machineSearch, batchesByMachine]);

  const totalMachinesWithQueue = useMemo(() => {
    return Object.keys(batchesByMachine).filter(m => batchesByMachine[m].length > 0).length;
  }, [batchesByMachine]);

  const totalQueuedBatches = useMemo(() => {
    return Object.values(batchesByMachine).reduce((acc, curr) => acc + curr.length, 0);
  }, [batchesByMachine]);

  // Drag and Drop Handler: supports reversed visual order towards the machine on the right
  const onDragEnd = async (result) => {
    if (!result.destination) return;
    const { source, destination, draggableId } = result;

    if (source.droppableId === destination.droppableId && source.index === destination.index) {
      return;
    }

    const destCol = destination.droppableId;
    let newStatus = 'QUEUED';
    let newMachine = null;
    let calculatedPos = destination.index + 1;

    if (destCol === 'PLANNING') {
      newStatus = 'PLANNING';
      calculatedPos = destination.index + 1;
    } else if (destCol.startsWith('MACHINE_')) {
      newMachine = destCol.replace('MACHINE_', '');
      newStatus = 'QUEUED';

      const targetItems = batchesByMachine[newMachine.toUpperCase()] || [];
      const totalLen = source.droppableId === destination.droppableId 
        ? targetItems.length 
        : targetItems.length + 1;

      // In the machine lane, items are displayed reversed:
      // index totalLen - 1 (closest to machine on right) = #1 (position 1)
      // index 0 (furthest from machine on left) = #totalLen (last in queue)
      calculatedPos = Math.max(1, totalLen - destination.index);
    }

    setBatches(prev => prev.map(b => {
      if (b.id === draggableId) {
        return {
          ...b,
          status: newStatus,
          ...(newMachine ? { machine_no: newMachine } : {}),
          position: calculatedPos
        };
      }
      return b;
    }));

    try {
      const payload = {
        status: newStatus,
        position: calculatedPos
      };
      if (newMachine) {
        payload.machine_no = newMachine;
      }
      await axios.put(`${API_BASE}/${draggableId}`, payload);
      fetchBatches();
    } catch (err) {
      console.error('Gagal memperbarui alokasi batch:', err);
      fetchBatches();
    }
  };

  const handleQuickAssign = async (batchId, targetMachine) => {
    try {
      await axios.put(`${API_BASE}/${batchId}`, {
        status: 'QUEUED',
        machine_no: targetMachine,
        position: 1 // Assigned as next or queue
      });
      toast.success(`Batch dipindahkan ke antrean ${targetMachine}.`);
      fetchBatches();
    } catch (err) {
      toast.error('Gagal memindahkan batch ke mesin: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleStatusChange = async (batchId, newStatus) => {
    try {
      await axios.put(`${API_BASE}/${batchId}`, { status: newStatus });
      fetchBatches();
    } catch (err) {
      toast.error('Gagal mengubah status batch: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCreateBatch = async (e) => {
    e.preventDefault();
    if (!form.batch_no.trim()) {
      toast.warning('Mohon isi Nomor Batch terlebih dahulu.');
      return;
    }

    try {
      await axios.post(`${API_BASE}/`, form);
      setIsModalOpen(false);
      toast.success(`Batch #${form.batch_no} berhasil dibuat.`);
      setForm({
        batch_no: '',
        reference_no: '',
        machine_no: form.machine_no,
        program_no: form.program_no,
        recipe_name: 'Reactive Dyeing Standard Formula',
        customer: 'PT. SMM JETFLOW',
        article: 'CM 30S RIB 100% Cotton',
        color_code: '1650159',
        color_name: 'UNGU TUA',
        fabric_weight_kg: 350.0,
        liquor_ratio: 8.0,
        status: 'PLANNING'
      });
      fetchBatches();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Gagal membuat batch baru.');
    }
  };

  const handleDeleteBatch = async (batchId, batchNo) => {
    const ok = await confirm(`Yakin ingin menghapus Batch #${batchNo}?`, {
      title: 'Hapus Batch',
      confirmText: 'Ya, Hapus',
      danger: true,
    });
    if (!ok) return;
    try {
      await axios.delete(`${API_BASE}/${batchId}`);
      setBatches(batches.filter(b => b.id !== batchId));
      toast.success(`Batch #${batchNo} berhasil dihapus.`);
    } catch (err) {
      toast.error('Gagal menghapus batch.');
    }
  };

  const handleDownloadZip = (batchId) => {
    window.location.href = `${API_BASE}/export-zip/${batchId}`;
  };

  const handleDownloadQueueZip = (machNo) => {
    window.location.href = `${API_BASE}/export-queue/${machNo}`;
  };

  const handleExecuteDispatch = async () => {
    if (!batchToDispatch) return;
    if (batchToDispatch.machine_no !== 'DA01' && batchToDispatch.machine_no !== 'M_95') {
      toast.warning('Pengiriman FTP dibatasi HANYA untuk Mesin DA01/M_95.', { title: 'Peringatan Keamanan' });
      return;
    }
    setIsDispatching(true);
    try {
      let targetDir = '/Network/F/OT/BATCH';
      if (dispatchModel === '797') {
        targetDir = '/Flashdisk/SC797CE/BATCH';
      } else if (dispatchModel === '777') {
        targetDir = '/Storage/sc777ce/BATCH';
      }
      const res = await axios.post('/api/ftp/dispatch-batch', {
        ip: dispatchIp.trim(),
        port: 21,
        batch_id: batchToDispatch.id,
        controller_type: dispatchModel,
        target_dir: targetDir
      });
      toast.success(res.data.message || `Batch ${batchToDispatch.batch_no} berhasil dikirim ke Kontroler FTP!`);
      setFtpDispatchModalOpen(false);
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      toast.error('Gagal mengirim batch via FTP: ' + msg);
    } finally {
      setIsDispatching(false);
    }
  };

  useEffect(() => {
    if (!isModalOpen && !ftpDispatchModalOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setIsModalOpen(false);
        setFtpDispatchModalOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isModalOpen, ftpDispatchModalOpen]);

  const totalWater = (form.fabric_weight_kg * form.liquor_ratio).toFixed(1);

  return (
    <div className={compactDensity ? 'space-y-2 text-[11px]' : 'space-y-3 text-xs'}>
      {/* MODERN READABLE HEADER WITH DENSITY TOGGLE */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-white dark:bg-boxdark px-3.5 py-2 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm tracking-tight text-black dark:text-white">
            Planning Board
          </span>
          <span className="text-[11px] text-body dark:text-bodydark font-mono hidden md:inline">
            · {batches.length} Batch ({totalQueuedBatches} Antrean)
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setCompactDensity((v) => !v)}
            className="px-2.5 py-1 rounded-lg border border-stroke dark:border-strokedark bg-gray dark:bg-meta-4 text-[11px] font-semibold text-black dark:text-white hover:bg-gray-200 dark:hover:bg-meta-4/80 transition"
            title="Ubah kerapatan kartu Kanban"
          >
            {compactDensity ? 'Mode Nyaman' : 'Mode Padat'}
          </button>

          <button
            type="button"
            onClick={handleSyncDB}
            disabled={syncing}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-blue-500/40 bg-blue-50/40 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400 text-[11px] font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/40 transition"
            title="Sinkronkan DB"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>

          <button
            type="button"
            onClick={fetchBatches}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-stroke bg-white dark:border-strokedark dark:bg-boxdark text-[11px] font-semibold text-black dark:text-white hover:bg-gray dark:hover:bg-meta-4 transition"
            title="Muat Ulang"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1 px-3 py-1 rounded-lg bg-primary hover:bg-primary/90 text-white text-[11px] font-bold shadow-xs transition"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>+ Batch</span>
          </button>
        </div>
      </div>

      {/* DRAG AND DROP CONTEXT (RESPONSIVE 2-COLUMN LAYOUT) */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex flex-col lg:flex-row items-stretch lg:items-start gap-3">
          
          {/* ========================================================================= */}
          {/* KOLOM 1 (KIRI): PERENCANAAN (PLANNING)                                    */}
          {/* ========================================================================= */}
          <div className={`${compactDensity ? 'w-full lg:w-64' : 'w-full lg:w-72'} shrink-0 flex flex-col rounded-xl border border-stroke dark:border-strokedark bg-gray-50/90 dark:bg-[#182234] p-3 shadow-xs`}>
            {/* Header Perencanaan */}
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-stroke dark:border-strokedark">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-500 ring-2 ring-purple-500/20" />
                <span className="font-bold text-xs text-black dark:text-white uppercase tracking-wide">
                  Perencanaan
                </span>
              </div>
              <span className="flex h-5 px-2 items-center justify-center rounded-full bg-purple-500/20 text-purple-600 dark:text-purple-400 text-[11px] font-black">
                {planningBatches.length}
              </span>
            </div>

            {/* Quick Search Planning */}
            <div className="mb-2.5 relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-gray-400" />
              <input
                type="text"
                placeholder="Cari batch..."
                value={planningSearch}
                onChange={(e) => setPlanningSearch(e.target.value)}
                className="w-full pl-8 pr-2.5 py-1.5 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-xs text-black dark:text-white focus:border-primary focus:outline-none"
              />
            </div>

            {/* Droppable Area: Kolom Planning (Vertical) */}
            <Droppable droppableId="PLANNING" direction="vertical">
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={`flex-1 space-y-2 p-1 rounded-lg transition-colors max-h-[820px] overflow-y-auto ${
                    snapshot.isDraggingOver ? 'bg-purple-500/10 border border-dashed border-purple-500/50' : ''
                  }`}
                >
                  {planningBatches.map((item, index) => (
                    <Draggable key={item.id} draggableId={item.id} index={index}>
                      {(provided, snapshot) => (
                        <div
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                          className={`rounded-lg border border-stroke bg-white ${compactDensity ? 'p-2' : 'p-2.5'} shadow-xs dark:border-strokedark dark:bg-boxdark transition-all select-none ${
                            snapshot.isDragging 
                              ? 'shadow-xl ring-2 ring-purple-500 scale-102 z-9999' 
                              : 'hover:border-purple-500/50'
                          }`}
                        >
                          {/* Row 1: Lot & Ref */}
                          <div className="flex items-center justify-between gap-1.5 leading-snug mb-1">
                            <span className="font-black text-xs text-purple-600 dark:text-purple-400 truncate max-w-[140px]" title={item.batch_no}>
                              #{item.batch_no}
                            </span>
                            <span className="text-[11px] font-mono text-gray-400 shrink-0">
                              {item.reference_no}
                            </span>
                          </div>

                          {/* Row 2: Recipe Title */}
                          <p className="text-xs font-bold text-black dark:text-white truncate line-clamp-1 leading-snug mb-1" title={item.recipe_name}>
                            {item.recipe_name}
                          </p>

                          {/* Row 3: Specs in 1 line */}
                          <div className="text-[11px] text-gray-400 truncate leading-snug mb-2">
                            <span className="text-gray-700 dark:text-gray-300 font-semibold">{item.article || '-'}</span> · <span className="text-primary font-semibold">{item.color_name}</span> · <span className="font-mono">{item.fabric_weight_kg}kg</span>
                          </div>

                          {/* Row 4: Action & Assign */}
                          <div className="pt-1.5 border-t border-stroke/50 dark:border-strokedark/50 flex items-center justify-between gap-1.5">
                            <select
                              defaultValue=""
                              onChange={(e) => {
                                if (e.target.value) {
                                  handleQuickAssign(item.id, e.target.value);
                                }
                              }}
                              className="flex-1 py-1 px-1.5 text-[11px] font-bold rounded-md border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-gray-800 dark:text-gray-200 focus:border-primary focus:outline-none cursor-pointer"
                            >
                              <option value="" disabled>Ke Mesin...</option>
                              <option value="DA01">DA01</option>
                              <option value="M_95">M_95</option>
                              {machineList
                                .filter(m => m.machine_no !== 'DA01' && m.machine_no !== 'M_95')
                                .map(m => (
                                  <option key={m.machine_no} value={m.machine_no}>{m.machine_no}</option>
                                ))}
                            </select>

                            <button
                              type="button"
                              onClick={() => handleDownloadZip(item.id)}
                              className="p-1.5 text-primary hover:bg-primary/10 rounded-md transition"
                              title="Unduh ZIP"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </button>

                            <button
                              type="button"
                              onClick={() => handleDeleteBatch(item.id, item.batch_no)}
                              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-500/10 rounded-md transition"
                              title="Hapus Batch"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      )}
                    </Draggable>
                  ))}

                  {provided.placeholder}

                  {planningBatches.length === 0 && (
                    <div className="h-24 flex flex-col items-center justify-center text-center p-3 text-gray-400 text-xs border border-dashed border-stroke dark:border-strokedark rounded-lg">
                      <span>Kosong</span>
                    </div>
                  )}
                </div>
              )}
            </Droppable>
          </div>

          {/* ========================================================================= */}
          {/* KOLOM 2 (KANAN): ANTREAN MESIN                                            */}
          {/* Menempel ke mesin di kanan: Yang paling dekat = #1 (pertama), paling jauh = terakhir */}
          {/* ========================================================================= */}
          <div className="flex-1 min-w-0 space-y-1">
            
            {/* Filter Toolbar Ringkas */}
            <div className="bg-white dark:bg-boxdark px-2.5 py-1.5 rounded-lg border border-stroke dark:border-strokedark shadow-xs flex flex-wrap items-center justify-between gap-2 text-[11px]">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-bold text-gray-400 text-[10px] uppercase">Filter:</span>
                
                <button
                  type="button"
                  onClick={() => {
                    setMachineFilterType('KEY_MACHINES');
                    setSelectedGroup('SEMUA');
                  }}
                  className={`px-2 py-1 rounded-md font-bold transition shrink-0 ${
                    machineFilterType === 'KEY_MACHINES'
                      ? 'bg-primary text-white shadow-xs'
                      : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-meta-4/80'
                  }`}
                >
                  DA01 & M_95
                </button>

                <button
                  type="button"
                  onClick={() => setMachineFilterType('WITH_QUEUES')}
                  className={`px-2 py-1 rounded-md font-bold transition shrink-0 flex items-center gap-1 ${
                    machineFilterType === 'WITH_QUEUES'
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-meta-4/80'
                  }`}
                >
                  <span>Ada Antrean ({totalMachinesWithQueue})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setMachineFilterType('ALL')}
                  className={`px-2 py-1 rounded-md font-bold transition shrink-0 ${
                    machineFilterType === 'ALL'
                      ? 'bg-primary text-white shadow-xs'
                      : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-meta-4/80'
                  }`}
                >
                  Semua ({machineList.length})
                </button>

                <div className="flex items-center gap-1.5 pl-1 border-l border-stroke dark:border-strokedark">
                  <label
                    htmlFor="board-jalur-filter"
                    className="font-bold text-gray-400 text-[10px] uppercase shrink-0"
                  >
                    Jalur:
                  </label>
                  <select
                    id="board-jalur-filter"
                    value={selectedGroup}
                    onChange={(e) => handleSelectGroup(e.target.value)}
                    className="py-1 px-2 rounded-md border border-stroke dark:border-strokedark bg-gray-50 dark:bg-boxdark-2 text-[11px] font-semibold text-black dark:text-white focus:border-primary focus:outline-none cursor-pointer"
                    title="Filter mesin berdasarkan jalur / area"
                  >
                    <option value="SEMUA">Semua Jalur ({machineList.length})</option>
                    {availableGroups
                      .filter((g) => g !== 'SEMUA')
                      .map((g) => (
                        <option key={g} value={g}>
                          {g} ({groupCounts[g] || 0})
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              <div className="relative shrink-0">
                <Search className="absolute left-2 top-1.5 h-3 w-3 text-gray-400" />
                <input
                  type="text"
                  placeholder="Cari mesin..."
                  value={machineSearch}
                  onChange={(e) => setMachineSearch(e.target.value)}
                  className="pl-6 pr-2 py-1 rounded-md border border-stroke dark:border-strokedark bg-gray-50 dark:bg-boxdark-2 text-[11px] text-black dark:text-white focus:border-primary focus:outline-none w-32 sm:w-40"
                />
              </div>
            </div>

            {/* DAFTAR BARIS MESIN (SWIMLANES): JALUR ANTREAN DI KIRI, BLOK MESIN DI UJUNG KANAN */}
            <div className={compactDensity ? 'space-y-1.5' : 'space-y-2.5'}>
              {displayedMachines.map((m) => {
                const machNo = m.machine_no;
                // items is sorted position ascending: items[0] is #1, items[last] is #N
                const items = batchesByMachine[machNo.toUpperCase()] || [];
                const isDA01 = machNo === 'DA01' || machNo === 'M_95';

                return (
                  <div 
                    key={machNo}
                    className={`flex flex-row items-stretch rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-[#182234] shadow-xs overflow-hidden transition-all hover:border-primary/40 ${compactDensity ? 'min-h-[78px]' : 'min-h-[104px]'}`}
                  >
                    {/* ========================================================= */}
                    {/* BAGIAN KIRI/TENGAH: JALUR ANTREAN MENEMPEL KE MESIN DI KANAN */}
                    {/* Yang paling dekat mesin (kanan) = #1, yang paling jauh (kiri) = terakhir */}
                    {/* ========================================================= */}
                    <Droppable droppableId={`MACHINE_${machNo}`} direction="horizontal">
                      {(provided, snapshot) => {
                        // Reverse array for display: displayItems[last] is items[0] (#1, closest to machine)
                        const displayItems = [...items].reverse();

                        return (
                          <div
                            ref={provided.innerRef}
                            {...provided.droppableProps}
                            className={`flex-1 flex flex-row items-stretch gap-2 p-2 overflow-x-auto transition-colors ${
                              snapshot.isDraggingOver 
                                ? 'bg-primary/10 border-2 border-dashed border-primary/50' 
                                : 'bg-slate-50/40 dark:bg-[#101726]/60'
                            }`}
                          >
                            {items.length === 0 ? (
                              <div className={`w-full h-full ${compactDensity ? 'min-h-[60px]' : 'min-h-[84px]'} flex items-center justify-center p-2 border border-dashed border-stroke/60 dark:border-strokedark/60 rounded-lg text-gray-400 text-xs`}>
                                <span>Antrean Kosong · Tarik batch ke sini</span>
                              </div>
                            ) : (
                              // ml-auto pushes all cards to the right against the machine block!
                              <div className="ml-auto pointer-events-none" />
                            )}

                            {displayItems.map((item, index) => {
                              const statusMeta = STATUS_CONFIG[item.status] || STATUS_CONFIG.QUEUED;
                              // The rightmost item (index === displayItems.length - 1) is #1
                              const queuePos = displayItems.length - index;
                              const isFirstInQueue = queuePos === 1;

                              return (
                                <Draggable key={item.id} draggableId={item.id} index={index}>
                                  {(provided, snapshot) => (
                                    <div
                                      ref={provided.innerRef}
                                      {...provided.draggableProps}
                                      {...provided.dragHandleProps}
                                      className={`${compactDensity ? 'w-[155px] p-1.5' : 'w-[185px] p-2.5'} shrink-0 rounded-lg border shadow-xs dark:bg-boxdark flex flex-col justify-between select-none transition-all ${
                                        isFirstInQueue 
                                          ? 'border-primary ring-1 ring-primary/40 bg-primary/5 dark:bg-primary/10' 
                                          : 'border-stroke bg-white dark:border-strokedark'
                                      } ${
                                        snapshot.isDragging 
                                          ? 'shadow-xl ring-2 ring-primary scale-102 z-9999' 
                                          : 'hover:border-primary/50'
                                      }`}
                                    >
                                      <div>
                                        {/* Row 1: Index + Lot No + Status */}
                                        <div className="flex items-center justify-between gap-1 leading-snug mb-1">
                                          <div className="flex items-center gap-1 truncate">
                                            <span className={`text-[10px] font-black px-1.5 py-0.5 rounded shrink-0 ${
                                              isFirstInQueue ? 'bg-primary text-white shadow-xs' : 'bg-gray-200 dark:bg-meta-4 text-gray-700 dark:text-gray-300'
                                            }`}>
                                              #{queuePos}
                                            </span>
                                            <span className="font-black text-xs text-primary truncate" title={item.batch_no}>
                                              {item.batch_no}
                                            </span>
                                          </div>

                                          <select
                                            value={item.status || 'QUEUED'}
                                            onChange={(e) => handleStatusChange(item.id, e.target.value)}
                                            className={`text-[10px] font-bold px-1 py-0.5 rounded border focus:outline-none cursor-pointer ${statusMeta.color} shrink-0`}
                                          >
                                            <option value="QUEUED">Q</option>
                                            <option value="WAITING_LA">LA</option>
                                            <option value="RUNNING">RUN</option>
                                            <option value="COMPLETED">DONE</option>
                                            <option value="PLANNING">PLAN</option>
                                          </select>
                                        </div>

                                        {/* Row 2: Recipe Name / Program */}
                                        <p className="text-xs font-bold text-black dark:text-white truncate leading-snug mb-0.5" title={item.recipe_name}>
                                          {item.recipe_name}
                                        </p>

                                        {/* Row 3: Specs */}
                                        <div className="text-[11px] text-gray-400 font-mono truncate leading-snug">
                                          {item.reference_no} · {item.fabric_weight_kg}kg
                                        </div>
                                      </div>

                                      {/* Action Row */}
                                      <div className="pt-1.5 border-t border-stroke/50 dark:border-strokedark/50 flex items-center justify-between gap-1 mt-1.5">
                                        {isDA01 ? (
                                          <button
                                            type="button"
                                            onClick={() => {
                                              setBatchToDispatch(item);
                                              setDispatchIp('192.168.1.95');
                                              setDispatchModel('network_ot');
                                              setFtpDispatchModalOpen(true);
                                            }}
                                            className="px-2 py-0.5 rounded-md bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold border border-emerald-500/20 transition"
                                            title="Kirim FTP DA01"
                                          >
                                            FTP
                                          </button>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => handleStatusChange(item.id, 'PLANNING')}
                                            className="px-2 py-0.5 rounded-md bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 text-[10px] font-bold border border-purple-500/20 transition"
                                            title="Kembalikan ke Planning"
                                          >
                                            Plan
                                          </button>
                                        )}

                                        <div className="flex items-center gap-1">
                                          <button
                                            type="button"
                                            onClick={() => handleDownloadZip(item.id)}
                                            className="p-1 text-primary hover:bg-primary/10 rounded-md transition"
                                            title="Unduh ZIP"
                                          >
                                            <Download className="h-3.5 w-3.5" />
                                          </button>

                                          <button
                                            type="button"
                                            onClick={() => handleDeleteBatch(item.id, item.batch_no)}
                                            className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-500/10 rounded-md transition"
                                            title="Hapus Batch"
                                          >
                                            <Trash2 className="h-3.5 w-3.5" />
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </Draggable>
                              );
                            })}

                            {provided.placeholder}
                          </div>
                        );
                      }}
                    </Droppable>

                    {/* ========================================================= */}
                    {/* BAGIAN UJUNG KANAN: IDENTITAS MESIN (MENEMPEL DI SISI KANAN!) */}
                    {/* ========================================================= */}
                    <div className={`${compactDensity ? 'w-32 sm:w-36 p-2' : 'w-36 sm:w-44 p-2.5'} shrink-0 bg-slate-50 dark:bg-[#151d2c] flex flex-col justify-between items-center text-center border-l border-stroke dark:border-strokedark`}>
                      <div className="w-full">
                        {/* Nama Mesin & Badge */}
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="text-sm font-black font-mono tracking-tight text-primary">
                            {machNo}
                          </span>
                          <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                            items.length > 0
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                              : 'bg-gray-200 dark:bg-meta-4 text-gray-500'
                          }`}>
                            {items.length}
                          </span>
                        </div>

                        <div className="text-[11px] text-gray-400 font-mono truncate">
                          {m.ip_address || '172.16.110.100'}
                        </div>
                      </div>

                      {/* Tombol aksi mesin di ujung kanan */}
                      <div className="w-full mt-2 pt-2 border-t border-stroke/50 dark:border-strokedark/50 space-y-1.5">
                        {isDA01 ? (
                          <button
                            type="button"
                            onClick={() => handleBulkSendToHmi(machNo)}
                            disabled={isBulkSending || items.length === 0}
                            className="w-full flex items-center justify-center gap-1 py-1 px-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-[11px] font-bold shadow-xs transition leading-none"
                            title="Kirim bulk antrean ke HMI"
                          >
                            <Send className={`h-3 w-3 ${isBulkSending ? 'animate-spin' : ''}`} />
                            <span>Kirim HMI</span>
                          </button>
                        ) : (
                          <div className="text-[10px] text-gray-400 font-mono text-center leading-none py-0.5">
                            Read-Only
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={() => handleDownloadQueueZip(machNo)}
                          disabled={items.length === 0}
                          className="w-full flex items-center justify-center gap-1 py-1 px-2 rounded-md border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-50 dark:hover:bg-meta-4 text-[10px] font-bold text-gray-600 dark:text-gray-300 disabled:opacity-40 transition leading-none"
                          title="Unduh QUEUE.BTD"
                        >
                          <Download className="h-3 w-3" />
                          <span>QUEUE</span>
                        </button>
                      </div>
                    </div>

                  </div>
                );
              })}

              {displayedMachines.length === 0 && (
                <div className="p-6 text-center bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark text-gray-400 text-xs">
                  Tidak ada mesin cocok dengan filter saat ini.
                </div>
              )}
            </div>
          </div>
        </div>
      </DragDropContext>

      {/* MODAL: BUAT BATCH BARU */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Buat Planning Batch Baru"
          onClick={() => setIsModalOpen(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark rounded-xl shadow-2xl max-w-md w-full border border-stroke dark:border-strokedark overflow-hidden text-xs"
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/20">
              <div className="flex items-center gap-1">
                <Cpu className="h-3.5 w-3.5 text-primary" />
                <h3 className="font-bold text-xs text-black dark:text-white">
                  Buat Planning Batch Baru
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <form onSubmit={handleCreateBatch} className="p-3 space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-700 dark:text-gray-300 mb-0.5">
                    Nomor Batch Produksi *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="LOT-95-01 / PJT030"
                    value={form.batch_no}
                    onChange={(e) => setForm({ ...form, batch_no: e.target.value })}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs font-bold text-primary dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-gray-700 dark:text-gray-300 mb-0.5">
                    Mesin Target *
                  </label>
                  <select
                    value={form.machine_no}
                    onChange={(e) => setForm({ ...form, machine_no: e.target.value })}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs font-bold dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  >
                    <option value="DA01">DA01 - SETEX 797CE (192.168.1.95)</option>
                    <option value="M_95">M_95 - SETEX 797CE (192.168.1.95)</option>
                    {machineList
                      .filter(m => m.machine_no !== 'M_95' && m.machine_no !== 'DA01')
                      .map(m => (
                        <option key={m.machine_no} value={m.machine_no}>{m.machine_no} - {m.display_name}</option>
                      ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-0.5">
                    Program Mesin *
                  </label>
                  <select
                    value={form.program_no}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      const match = availablePrograms.find(p => p.no === val);
                      setForm({
                        ...form,
                        program_no: val,
                        ...(match && match.rawName ? { recipe_name: match.rawName } : {})
                      });
                    }}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs font-mono dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  >
                    {availablePrograms.map(p => (
                      <option key={p.no} value={p.no}>{p.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-0.5">
                    Nama Formula / Resep
                  </label>
                  <input
                    type="text"
                    value={form.recipe_name}
                    onChange={(e) => setForm({ ...form, recipe_name: e.target.value })}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-0.5">
                    Pelanggan
                  </label>
                  <input
                    type="text"
                    value={form.customer}
                    onChange={(e) => setForm({ ...form, customer: e.target.value })}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-0.5">
                    Artikel Kain
                  </label>
                  <input
                    type="text"
                    value={form.article}
                    onChange={(e) => setForm({ ...form, article: e.target.value })}
                    className="w-full rounded border border-stroke px-2 py-1 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 p-1.5 rounded bg-gray-50 dark:bg-meta-4/30 border border-stroke dark:border-strokedark text-[9px]">
                <div>
                  <label className="block text-gray-500 mb-0.5">Berat (Kg)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={form.fabric_weight_kg}
                    onChange={(e) => setForm({ ...form, fabric_weight_kg: Number(e.target.value) })}
                    className="w-full rounded border border-stroke px-1 py-0.5 text-xs font-bold dark:border-strokedark dark:bg-boxdark"
                  />
                </div>

                <div>
                  <label className="block text-gray-500 mb-0.5">Rasio (1:X)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    value={form.liquor_ratio}
                    onChange={(e) => setForm({ ...form, liquor_ratio: Number(e.target.value) })}
                    className="w-full rounded border border-stroke px-1 py-0.5 text-xs font-bold dark:border-strokedark dark:bg-boxdark"
                  />
                </div>

                <div>
                  <label className="block text-gray-500 mb-0.5">Volume Air</label>
                  <div className="rounded border border-stroke px-1 py-0.5 text-xs font-mono font-bold text-blue-600 dark:text-blue-400 bg-white dark:bg-boxdark">
                    {totalWater} L
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-1.5 pt-1.5 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-2.5 py-1 rounded border border-stroke dark:border-strokedark text-xs font-semibold hover:bg-gray-100"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 rounded bg-primary hover:bg-opacity-90 text-white text-xs font-bold shadow-xs"
                >
                  Simpan Batch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: FTP DISPATCH BATCH DIRECT TO CONTROLLER */}
      {ftpDispatchModalOpen && batchToDispatch && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Kirim Batch ke Mesin"
          onClick={() => setFtpDispatchModalOpen(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-xl w-full max-w-sm p-4 shadow-2xl space-y-2.5 text-xs"
          >
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-1.5">
              <h3 className="text-xs font-bold text-black dark:text-white flex items-center gap-1">
                <Send className="h-3 w-3 text-emerald-500" />
                Kirim Batch ke Mesin {batchToDispatch.machine_no}
              </h3>
              <button
                onClick={() => setFtpDispatchModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-1.5 text-[10px]">
              <div className="bg-gray-50 dark:bg-meta-4 p-1.5 rounded border border-stroke dark:border-strokedark space-y-0.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Batch:</span>
                  <strong className="text-black dark:text-white">#{batchToDispatch.batch_no} ({batchToDispatch.reference_no})</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Resep:</span>
                  <span className="text-emerald-600 dark:text-emerald-400 truncate max-w-[160px] font-semibold">{batchToDispatch.recipe_name}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-1.5 bg-gray-50 dark:bg-meta-4 p-1.5 rounded border border-stroke dark:border-strokedark">
                <div>
                  <label className="block text-gray-600 dark:text-gray-300 font-medium mb-0.5 text-[9px]">IP Kontroler:</label>
                  <input
                    type="text"
                    value={dispatchIp}
                    onChange={(e) => setDispatchIp(e.target.value)}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-strokedark text-black dark:text-emerald-400 font-mono font-bold rounded px-1.5 py-0.5 outline-none text-[9px]"
                  />
                </div>

                <div>
                  <label className="block text-gray-600 dark:text-gray-300 font-medium mb-0.5 text-[9px]">Folder Target:</label>
                  <select
                    value={dispatchModel}
                    onChange={(e) => setDispatchModel(e.target.value)}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-strokedark text-black dark:text-emerald-400 font-bold rounded px-1 py-0.5 outline-none text-[9px]"
                  >
                    <option value="network_ot">/Network/F/OT/BATCH/</option>
                    <option value="797">/Flashdisk/SC797CE/BATCH</option>
                    <option value="777">/Storage/sc777ce/BATCH</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-1 pt-1 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setFtpDispatchModalOpen(false)}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-meta-4 dark:hover:bg-meta-4/80 dark:text-white px-2 py-0.5 rounded text-[10px] border border-stroke dark:border-strokedark"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleExecuteDispatch}
                  disabled={isDispatching}
                  className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold px-2.5 py-0.5 rounded flex items-center gap-1 shadow-xs text-[10px]"
                >
                  <Send className={`h-2.5 w-2.5 ${isDispatching ? 'animate-spin' : ''}`} />
                  <span>{isDispatching ? '...' : 'Kirim'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default KanbanView;
