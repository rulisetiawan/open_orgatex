import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { 
  Plus, 
  Download, 
  Send,
  Clock, 
  Layers, 
  User, 
  RefreshCw, 
  ShieldAlert, 
  CheckCircle2, 
  Trash2, 
  FileCode, 
  Droplet, 
  X, 
  Cpu, 
  Tag, 
  Sparkles,
  Lock
} from 'lucide-react';
import axios from 'axios';

const API_BASE = '/api/planning';

const COLUMN_DEFS = {
  PLANNING: { name: 'Perencanaan (Planning)', color: 'border-purple-500/50 bg-purple-50/10 dark:bg-purple-950/20 text-purple-400' },
  QUEUED: { name: 'Antrean Produksi (Queued)', color: 'border-amber-500/50 bg-amber-50/10 dark:bg-amber-950/20 text-amber-500' },
  WAITING_LA: { name: 'Menunggu Dosing LA', color: 'border-blue-500/50 bg-blue-50/10 dark:bg-blue-950/20 text-blue-500' },
  RUNNING: { name: 'Sedang Proses Celup (Running)', color: 'border-emerald-500/50 bg-emerald-50/10 dark:bg-emerald-950/20 text-emerald-500' },
  COMPLETED: { name: 'Selesai (Completed)', color: 'border-slate-500/50 bg-slate-50/10 dark:bg-slate-900/30 text-slate-400' },
};

const KanbanView = () => {
  const [batches, setBatches] = useState([]);
  const [machineList, setMachineList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [selectedMachine, setSelectedMachine] = useState('SEMUA');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [availablePrograms, setAvailablePrograms] = useState([
    { no: 401, name: 'M_0401.PRG - Reactive Dyeing Standard' },
    { no: 182, name: 'M_0182.PRG - Cotton Scouring & Bleach' },
    { no: 502, name: 'M_0502.PRG - Disperse Poly Jet 130C' },
    { no: 1, name: 'M_0001.PRG - Quick Rinsing & Neutral' },
  ]);

  // Form State - Defaults to M_95 and PT. SMM JETFLOW
  const [form, setForm] = useState({
    batch_no: '',
    reference_no: '',
    machine_no: 'M_95',
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

  // Bulk Send Antrean to HMI Controller (Khusus Mesin DA01)
  const handleBulkSendToHmi = async () => {
    if (selectedMachine !== 'DA01') {
      alert('Peringatan Keamanan: Pengiriman massal (bulk) ke HMI hanya diizinkan untuk Mesin DA01. Mesin lain dalam mode read-only dan tidak diizinkan menulis.');
      return;
    }

    const queuedBatches = columnsData.QUEUED || [];
    if (queuedBatches.length === 0) {
      alert('Tidak ada batch di kolom Antrean Produksi (QUEUED) untuk mesin DA01.');
      return;
    }

    const confirmMsg = `Konfirmasi Kirim Bulk ke HMI DA01 (192.168.1.95):\n\n` +
      `Sistem akan mengompilasi ${queuedBatches.length} batch antrean ke berkas QUEUE.BTD dan mengunggahnya ke kontroler HMI mesin DA01.\n` +
      `Seluruh berkas biner PRG dan BATCHREF.REF juga akan disinkronkan.\n\n` +
      `Apakah Anda yakin ingin mereplace antrean di HMI DA01 sekarang?`;

    if (!window.confirm(confirmMsg)) return;

    setIsBulkSending(true);
    try {
      const res = await axios.post('/api/ftp/bulk-replace-queue', {
        machine_no: 'DA01',
        ip: '192.168.1.95',
        port: 21
      });
      alert(res.data.message || `Berhasil mengirim ${queuedBatches.length} batch antrean ke HMI DA01!`);
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      alert('Gagal mengirim antrean ke HMI DA01: ' + msg);
    } finally {
      setIsBulkSending(false);
    }
  };

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/`);
      setBatches(res.data);
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
            name: `M_${String(pNo).padStart(4, '0')}.PRG - ${pName} (${p.machine_code || 'SETEX'} · ${p.total_steps || 0} Step)`,
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
      if (res.data && Array.isArray(res.data)) {
        setMachineList(res.data);
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

  const machineOptions = React.useMemo(() => {
    const list = ['SEMUA', 'M_95', 'DA01'];
    machineList.forEach(m => {
      if (!list.includes(m.machine_no)) {
        list.push(m.machine_no);
      }
    });
    return list;
  }, [machineList]);

  // Sync PostgreSQL & SQLite
  const handleSyncDB = async () => {
    setSyncing(true);
    try {
      const res = await axios.post('/api/database/sync');
      alert(res.data.message || 'Sinkronisasi PostgreSQL & SQLite selesai!');
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      alert('Gagal sinkronisasi DB: ' + msg);
    } finally {
      setSyncing(false);
    }
  };

  // Filter batches by machine
  const filteredBatches = selectedMachine === 'SEMUA' 
    ? batches 
    : batches.filter(b => b.machine_no === selectedMachine);

  // Group by Column Status
  const columnsData = {
    PLANNING: filteredBatches.filter(b => (b.status || '').toUpperCase() === 'PLANNING').sort((a,b) => (a.position || 0) - (b.position || 0)),
    QUEUED: filteredBatches.filter(b => (b.status || '').toUpperCase() === 'QUEUED').sort((a,b) => (a.position || 0) - (b.position || 0)),
    WAITING_LA: filteredBatches.filter(b => (b.status || '').toUpperCase() === 'WAITING_LA').sort((a,b) => (a.position || 0) - (b.position || 0)),
    RUNNING: filteredBatches.filter(b => (b.status || '').toUpperCase() === 'RUNNING').sort((a,b) => (a.position || 0) - (b.position || 0)),
    COMPLETED: filteredBatches.filter(b => (b.status || '').toUpperCase() === 'COMPLETED').sort((a,b) => (a.position || 0) - (b.position || 0)),
  };

  const onDragEnd = async (result) => {
    if (!result.destination) return;
    const { source, destination, draggableId } = result;

    if (source.droppableId === destination.droppableId && source.index === destination.index) {
      return;
    }

    const newStatus = destination.droppableId;
    const updated = batches.map(b => b.id === draggableId ? { ...b, status: newStatus } : b);
    setBatches(updated);

    try {
      await axios.put(`${API_BASE}/${draggableId}`, { status: newStatus });
    } catch (err) {
      console.error('Gagal memperbarui status batch:', err);
      fetchBatches(); // Rollback on error
    }
  };

  const handleCreateBatch = async (e) => {
    e.preventDefault();
    if (!form.batch_no.trim()) {
      alert('Mohon isi Nomor Batch!');
      return;
    }

    try {
      await axios.post(`${API_BASE}/`, form);
      setIsModalOpen(false);
      // Reset form defaults
      setForm({
        batch_no: '',
        reference_no: '',
        machine_no: form.machine_no,
        program_no: form.program_no,
        recipe_name: 'Reactive Dyeing Formula',
        customer: 'PT. ARTA PERMAI',
        article: 'CM 30S RIB 100% Cotton',
        color_code: '1650159',
        color_name: 'UNGU TUA',
        fabric_weight_kg: 325.85,
        liquor_ratio: 8.0,
        status: 'PLANNING'
      });
      fetchBatches();
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal membuat batch baru.');
    }
  };

  const handleDeleteBatch = async (batchId, batchNo) => {
    if (!window.confirm(`Yakin ingin menghapus Batch #${batchNo} dari antrean?`)) return;
    try {
      await axios.delete(`${API_BASE}/${batchId}`);
      setBatches(batches.filter(b => b.id !== batchId));
    } catch (err) {
      alert('Gagal menghapus batch.');
    }
  };

  const handleDownloadZip = (batchId, refNo, batchNo) => {
    // Direct browser download without touching network share
    window.location.href = `${API_BASE}/export-zip/${batchId}`;
  };

  // Dispatch Batch Directly to Controller via FTP
  const handleExecuteDispatch = async () => {
    if (!batchToDispatch) return;
    if (batchToDispatch.machine_no !== 'DA01') {
      alert(`Peringatan Keamanan: Pengiriman FTP dibatasi HANYA untuk Mesin DA01. Mesin ${batchToDispatch.machine_no} dalam mode Read-Only.`);
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
      alert(res.data.message || `Batch ${batchToDispatch.batch_no} berhasil dikirim ke Kontroler FTP!`);
      setFtpDispatchModalOpen(false);
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      alert('Gagal mengirim batch via FTP: ' + msg);
    } finally {
      setIsDispatching(false);
    }
  };

  const totalWater = (form.fabric_weight_kg * form.liquor_ratio).toFixed(1);

  return (
    <div className="space-y-6">
      {/* HEADER & SAFETY BANNER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-black tracking-tight text-black dark:text-white">
              Batch Scheduler & Planning (SCX620)
            </h2>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/30">
              SETEX BATCHREF & QUEUE
            </span>
          </div>
          <p className="text-xs text-body dark:text-gray-400 mt-1">
            Manajemen antrean produksi, alokasi nomor referensi 6-digit, dan generator paket biner SECOM 777.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleSyncDB}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-2 rounded border border-blue-500/50 bg-blue-50/20 dark:bg-blue-950/30 text-blue-400 text-xs font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/40 transition"
            title="Sinkronkan data antara PostgreSQL pt_smm_jetflow dan SQLite lokal"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin text-blue-400' : 'text-blue-400'}`} />
            <span>{syncing ? 'Syncing...' : 'Sync DB'}</span>
          </button>

          <button
            onClick={fetchBatches}
            className="flex items-center gap-1.5 px-3 py-2 rounded border border-stroke bg-white dark:border-strokedark dark:bg-boxdark text-xs font-semibold hover:bg-gray-100 dark:hover:bg-meta-4 transition"
            title="Muat Ulang Data"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary hover:bg-opacity-90 text-white text-xs font-bold shadow-md transition"
          >
            <Plus className="h-4 w-4" />
            <span>+ Buat Batch Baru</span>
          </button>
        </div>
      </div>

      {/* MODE AMAN BANNER */}
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-50/20 dark:bg-emerald-950/20 p-3.5 flex items-start gap-3">
        <ShieldAlert className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
        <div className="text-xs">
          <span className="font-bold text-emerald-600 dark:text-emerald-400">Mode Aman Aktif (Read-Only Folder Bersama):</span>{' '}
          <span className="text-gray-600 dark:text-gray-300">
            Sesuai instruksi keamanan, sistem <strong>TIDAK menulis ke folder bersama / share jaringan mesin</strong>. 
            Semua antrean disimpan di database lokal dan dapat diunduh kapan saja sebagai berkas paket biner ZIP (berisi <code>BATCHREF.REF</code> 762-byte & <code>M_xxxx.PRG</code>) untuk verifikasi mandiri.
          </span>
        </div>
      </div>

      {/* FILTER MESIN */}
      <div className="flex items-center justify-between bg-white dark:bg-boxdark p-3 rounded-lg border border-stroke dark:border-strokedark">
        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wider pl-1">Pilih Mesin:</span>
          {machineOptions.map(m => (
            <button
              key={m}
              onClick={() => setSelectedMachine(m)}
              className={`px-3 py-1 rounded text-xs font-bold transition ${
                selectedMachine === m
                  ? 'bg-primary text-white shadow'
                  : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 hover:bg-gray-200'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
        <div className="text-xs text-gray-500">
          Total: <strong className="text-primary">{filteredBatches.length}</strong> Batch
        </div>
      </div>

      {/* KANBAN BOARD */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {Object.entries(COLUMN_DEFS).map(([colKey, colMeta]) => {
            const items = columnsData[colKey] || [];
            return (
              <div 
                key={colKey}
                className="flex flex-col rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-[#182234] p-3 min-h-[500px]"
              >
                {/* Column Header */}
                <div className={`flex items-center justify-between pb-2.5 mb-2.5 border-b border-stroke dark:border-strokedark`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full bg-current ${colMeta.color}`} />
                    <h3 className="font-bold text-xs uppercase tracking-wider text-black dark:text-white">
                      {colMeta.name}
                    </h3>
                  </div>
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary text-[11px] font-bold">
                    {items.length}
                  </span>
                </div>

                {/* Bulk Send to HMI Button for QUEUED column */}
                {colKey === 'QUEUED' && (
                  <div className="mb-3">
                    {selectedMachine === 'DA01' ? (
                      <button
                        type="button"
                        onClick={handleBulkSendToHmi}
                        disabled={isBulkSending || items.length === 0}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow transition"
                        title="Tulis ulang QUEUE.BTD dan berkas biner di HMI Mesin DA01 (192.168.1.95) secara bulk"
                      >
                        <Send className={`h-3.5 w-3.5 ${isBulkSending ? 'animate-spin' : ''}`} />
                        <span>{isBulkSending ? 'Mengirim ke HMI...' : 'Kirim ke HMI DA01 (Bulk)'}</span>
                      </button>
                    ) : (
                      <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-[10px] font-medium">
                        <span className="flex items-center gap-1">
                          <Lock className="h-3 w-3 shrink-0" />
                          Kirim HMI (Hanya DA01)
                        </span>
                        <span className="text-[9px] uppercase font-bold px-1 rounded bg-amber-500/20">Read-Only</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Droppable Area */}
                <Droppable droppableId={colKey}>
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`flex-1 space-y-3 p-1 rounded-lg transition-colors ${
                        snapshot.isDraggingOver ? 'bg-primary/5 dark:bg-meta-4/20' : ''
                      }`}
                    >
                      {items.map((item, index) => (
                        <Draggable key={item.id} draggableId={item.id} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              className={`rounded-lg border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark transition-all select-none ${
                                snapshot.isDragging ? 'shadow-2xl ring-2 ring-primary rotate-1' : 'hover:border-primary/50'
                              }`}
                            >
                              {/* Top Bar: Batch No, Machine Tag & Ref */}
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-black text-sm text-primary">#{item.batch_no}</span>
                                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-gray-100 dark:bg-meta-4 text-gray-500 font-semibold">
                                      Ref: {item.reference_no}
                                    </span>
                                  </div>
                                  <span className="text-[10px] text-gray-400 font-semibold">
                                    Posisi Antrean: #{item.position || index + 1}
                                  </span>
                                </div>
                                <span className="text-[11px] px-2 py-0.5 rounded bg-primary/10 text-primary font-mono font-bold border border-primary/20">
                                  {item.machine_no}
                                </span>
                              </div>

                              {/* Recipe & Customer */}
                              <p className="text-xs font-bold text-black dark:text-white leading-snug line-clamp-2 mb-1">
                                {item.recipe_name}
                              </p>
                              <div className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400 mb-2">
                                <User className="h-3 w-3 shrink-0" />
                                <span className="truncate">{item.customer}</span>
                              </div>

                              {/* Fabric & Color Specs */}
                              <div className="rounded bg-gray-50 dark:bg-meta-4/40 p-2 text-[10px] space-y-1 mb-2.5">
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Artikel:</span>
                                  <span className="font-semibold text-gray-700 dark:text-gray-200 truncate max-w-[140px]">{item.article}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Warna:</span>
                                  <span className="font-semibold text-primary">{item.color_name} ({item.color_code})</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Program Mesin:</span>
                                  <span className="font-mono font-bold text-gray-800 dark:text-gray-100">M_{String(item.program_no).padStart(4, '0')}.PRG</span>
                                </div>
                              </div>

                              {/* Weight & Total Volume */}
                              <div className="flex items-center justify-between text-[11px] text-body pt-1 border-t border-stroke/60 dark:border-strokedark/60 mb-2.5">
                                <span className="flex items-center gap-1 font-semibold">
                                  <Layers className="h-3.5 w-3.5 text-primary" />
                                  {item.fabric_weight_kg} kg
                                </span>
                                <span className="flex items-center gap-1 text-gray-500 font-mono">
                                  <Droplet className="h-3.5 w-3.5 text-blue-500" />
                                  {item.total_water_l || Math.round(item.fabric_weight_kg * (item.liquor_ratio || 8))} L
                                </span>
                              </div>

                              {/* Bottom Action Buttons */}
                              <div className="flex items-center justify-between gap-1.5 pt-1">
                                {item.machine_no === 'DA01' ? (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setBatchToDispatch(item);
                                      setDispatchIp('192.168.1.95');
                                      setDispatchModel('network_ot');
                                      setFtpDispatchModalOpen(true);
                                    }}
                                    className="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold border border-emerald-500/20 transition"
                                    title="Kirim Batch ke Folder /Network/F/OT HMI DA01 (192.168.1.95)"
                                  >
                                    <Send className="h-3 w-3" />
                                    <span>Kirim FTP</span>
                                  </button>
                                ) : (
                                  <div 
                                    className="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-gray-100 dark:bg-meta-4 text-gray-400 text-[10px] font-medium cursor-not-allowed border border-dashed border-gray-300 dark:border-gray-700"
                                    title={`Mesin ${item.machine_no} dalam mode Read-Only. Hanya DA01 yang diizinkan menulis ke kontroler.`}
                                  >
                                    <Lock className="h-3 w-3" />
                                    <span>Terkunci</span>
                                  </div>
                                )}

                                <button
                                  type="button"
                                  onClick={() => handleDownloadZip(item.id, item.reference_no, item.batch_no)}
                                  className="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-primary/10 hover:bg-primary/20 text-primary text-[10px] font-bold border border-primary/20 transition"
                                  title="Unduh Paket Biner BATCHREF.REF & M_xxxx.PRG (ZIP)"
                                >
                                  <Download className="h-3 w-3" />
                                  <span>ZIP</span>
                                </button>

                                <button
                                  type="button"
                                  onClick={() => handleDeleteBatch(item.id, item.batch_no)}
                                  className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition"
                                  title="Hapus dari antrean"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}

                      {items.length === 0 && (
                        <div className="h-28 flex flex-col items-center justify-center text-gray-400 text-xs border border-dashed border-stroke dark:border-strokedark rounded-lg">
                          <span>Tidak ada batch</span>
                        </div>
                      )}
                    </div>
                  )}
                </Droppable>
              </div>
            );
          })}
        </div>
      </DragDropContext>

      {/* MODAL FORM BUAT BATCH BARU */}
      {isModalOpen && (
        <div className="fixed inset-0 z-9999 flex items-center justify-center bg-black/60 p-4 overflow-y-auto">
          <div className="bg-white dark:bg-boxdark rounded-xl shadow-2xl max-w-xl w-full border border-stroke dark:border-strokedark overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/20">
              <div className="flex items-center gap-2">
                <Cpu className="h-5 w-5 text-primary" />
                <h3 className="font-bold text-base text-black dark:text-white">
                  Buat Planning Batch Baru (OrgaTEX SCX620)
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Form Body */}
            <form onSubmit={handleCreateBatch} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                    Nomor Batch Produksi *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="misal PJT030"
                    value={form.batch_no}
                    onChange={(e) => setForm({ ...form, batch_no: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs font-bold text-primary dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                    Mesin Target *
                  </label>
                  <select
                    value={form.machine_no}
                    onChange={(e) => setForm({ ...form, machine_no: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs font-bold dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  >
                    <optgroup label="⭐ SETEX 797CE">
                      <option value="M_95">M_95 - SETEX 797CE Mesin DA01 (192.168.1.95)</option>
                      <option value="DA01">DA01 - SETEX 797CE Mesin DA01 (192.168.1.95)</option>
                    </optgroup>
                    {machineList.filter(m => m.machine_no !== 'M_95' && m.machine_no !== 'DA01').length > 0 && (
                      <optgroup label="Mesin Produksi Lainnya">
                        {machineList
                          .filter(m => m.machine_no !== 'M_95' && m.machine_no !== 'DA01')
                          .map(m => (
                            <option key={m.machine_no} value={m.machine_no}>
                              {m.machine_no} - {m.display_name} ({m.ip_address})
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Program Mesin (M_xxxx.PRG) *
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
                    className="w-full rounded border border-stroke px-3 py-2 text-xs font-mono dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  >
                    {availablePrograms.map(p => (
                      <option key={p.no} value={p.no}>{p.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Nama Formula / Resep
                  </label>
                  <input
                    type="text"
                    placeholder="misal Reactive Blue 60C"
                    value={form.recipe_name}
                    onChange={(e) => setForm({ ...form, recipe_name: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Pelanggan (Customer)
                  </label>
                  <input
                    type="text"
                    placeholder="PT. ARTA PERMAI"
                    value={form.customer}
                    onChange={(e) => setForm({ ...form, customer: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Artikel Kain (Fabric)
                  </label>
                  <input
                    type="text"
                    placeholder="CM 30S RIB"
                    value={form.article}
                    onChange={(e) => setForm({ ...form, article: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Kode Warna
                  </label>
                  <input
                    type="text"
                    placeholder="1650159"
                    value={form.color_code}
                    onChange={(e) => setForm({ ...form, color_code: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Deskripsi Warna
                  </label>
                  <input
                    type="text"
                    placeholder="UNGU TUA"
                    value={form.color_name}
                    onChange={(e) => setForm({ ...form, color_name: e.target.value })}
                    className="w-full rounded border border-stroke px-3 py-2 text-xs dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-gray-50 dark:bg-meta-4/30 border border-stroke dark:border-strokedark">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 mb-1">
                    Berat Kain (Kg)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={form.fabric_weight_kg}
                    onChange={(e) => setForm({ ...form, fabric_weight_kg: Number(e.target.value) })}
                    className="w-full rounded border border-stroke px-2.5 py-1.5 text-xs font-bold dark:border-strokedark dark:bg-boxdark focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 mb-1">
                    Rasio Air (1 : X)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    value={form.liquor_ratio}
                    onChange={(e) => setForm({ ...form, liquor_ratio: Number(e.target.value) })}
                    className="w-full rounded border border-stroke px-2.5 py-1.5 text-xs font-bold dark:border-strokedark dark:bg-boxdark focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 mb-1">
                    Total Volume Air
                  </label>
                  <div className="rounded border border-stroke px-2.5 py-1.5 text-xs font-mono font-bold text-blue-600 dark:text-blue-400 bg-white dark:bg-boxdark">
                    {totalWater} L
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                  Tahap Masuk Awal (Status) *
                </label>
                <select
                  value={form.status || 'PLANNING'}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full rounded border border-stroke px-3 py-2 text-xs font-bold dark:border-strokedark dark:bg-boxdark-2 focus:border-primary focus:outline-none"
                >
                  <option value="PLANNING">Perencanaan (PLANNING) - Masuk ke kolom Perencanaan (Tidak dikirim ke HMI)</option>
                  <option value="QUEUED">Antrean Produksi (QUEUED) - Masuk antrean siap jalan</option>
                </select>
                <span className="text-[10px] text-gray-400 block mt-1">
                  Batch berstatus "Perencanaan" disimpan di database dan belum dimasukkan ke antrean mesin / HMI.
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded border border-stroke dark:border-strokedark text-xs font-semibold hover:bg-gray-100 dark:hover:bg-meta-4 transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded bg-primary hover:bg-opacity-90 text-white text-xs font-bold shadow-md transition"
                >
                  Simpan ke Antrean
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: FTP DISPATCH BATCH DIRECT TO CONTROLLER */}
      {ftpDispatchModalOpen && batchToDispatch && (
        <div className="fixed inset-0 z-9999 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-gray-700 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Send className="h-5 w-5 text-emerald-400" />
                Kirim Batch ke Folder OrgaTEX (/Network/F/OT) - Kontroler DA01
              </h3>
              <button
                onClick={() => setFtpDispatchModalOpen(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div className="bg-[#24303f] p-3 rounded border border-gray-700 space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-400">Batch Target:</span>
                  <strong className="text-white">#{batchToDispatch.batch_no} (Ref: {batchToDispatch.reference_no})</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Resep / Formula:</span>
                  <span className="text-emerald-400">{batchToDispatch.recipe_name || 'Standard'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Nomor Program:</span>
                  <span className="text-amber-400">M_{String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 bg-[#24303f] p-3 rounded border border-gray-700">
                <div>
                  <label className="block text-gray-300 font-medium mb-1">IP Kontroler Target:</label>
                  <input
                    type="text"
                    value={dispatchIp}
                    onChange={(e) => {
                      const val = e.target.value;
                      setDispatchIp(val);
                      if (val.trim() === '192.168.1.95') {
                        setDispatchModel('network_ot');
                      }
                    }}
                    placeholder="192.168.1.95"
                    className="w-full bg-[#1c2434] border border-gray-600 text-emerald-400 font-mono font-bold rounded px-2.5 py-1.5 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 block mt-1">Default DA01: 192.168.1.95</span>
                </div>

                <div>
                  <label className="block text-gray-300 font-medium mb-1">Tipe Kontroler / Folder:</label>
                  <select
                    value={dispatchModel}
                    onChange={(e) => setDispatchModel(e.target.value)}
                    className="w-full bg-[#1c2434] border border-gray-600 text-emerald-400 font-bold rounded px-2.5 py-1.5 outline-none"
                  >
                    <option value="network_ot">OrgaTEX Share (/Network/F/OT/BATCH/ + QUEUE.BTD)</option>
                    <option value="797">SETEX 797CE Lokal (/Flashdisk/SC797CE/BATCH)</option>
                    <option value="777">SETEX 777 Lokal (/Storage/sc777ce/BATCH)</option>
                  </select>
                  <span className="text-[10px] text-gray-400 block mt-1">Standar OrgaTEX: /Network/F/OT</span>
                </div>
              </div>

              <div className="text-[11px] text-gray-400 bg-black/20 p-2.5 rounded border border-gray-800 space-y-1.5">
                <span className="font-bold text-gray-300">File biner yang langsung diunggah:</span>
                <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                  <li>Folder Batch: <code className="text-emerald-400 font-mono">
                    {dispatchModel === 'network_ot'
                      ? `/Network/F/OT/BATCH/${batchToDispatch.reference_no}/`
                      : (dispatchModel === '797' ? '/Flashdisk/SC797CE/BATCH/' : '/Storage/sc777ce/BATCH/')}
                  </code></li>
                  <li className="pl-4 text-gray-400">- <code className="text-emerald-300">BATCHREF.REF</code> (762-byte Secom binary structure)</li>
                  <li className="pl-4 text-gray-400">- <code className="text-emerald-300">M_{String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG</code> (Biner program mikro)</li>
                  {dispatchModel === 'network_ot' && (
                    <li>Append Antrean: <code className="text-cyan-400 font-mono">
                      /Network/F/OT/MACHINES/{batchToDispatch.machine_no || 'DA01'}/BATCHES/QUEUE.BTD
                    </code></li>
                  )}
                </ul>
                <div className="text-gray-400 pt-1 border-t border-gray-800">
                  Path remote: <strong className="text-emerald-400 font-mono">
                    {dispatchModel === 'network_ot' 
                      ? `/Network/F/OT/BATCH/${batchToDispatch.reference_no} & QUEUE.BTD` 
                      : (dispatchModel === '797' ? '/Flashdisk/SC797CE/BATCH' : '/Storage/sc777ce/BATCH')}
                  </strong>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-700">
                <button
                  type="button"
                  onClick={() => setFtpDispatchModalOpen(false)}
                  className="bg-gray-700 text-white px-3 py-1.5 rounded"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleExecuteDispatch}
                  disabled={isDispatching}
                  className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold px-4 py-1.5 rounded flex items-center gap-1.5 shadow"
                >
                  <Send className={`h-3.5 w-3.5 ${isDispatching ? 'animate-spin' : ''}`} />
                  <span>{isDispatching ? 'Mengirim ke FTP...' : `Kirim Batch ke ${dispatchIp}`}</span>
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
