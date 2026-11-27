import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ListFilter, 
  Plus, 
  Download, 
  Send, 
  RefreshCw, 
  Search, 
  Edit3, 
  Trash2, 
  ArrowUpDown, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Layers, 
  Droplet, 
  FileCode, 
  FileText,
  Cpu, 
  ExternalLink,
  Lock
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import BatchFormulaPreview from '../../components/Formulas/BatchFormulaPreview';
import { FABRIC_TYPE_OPTIONS, COLOR_SHADE_OPTIONS, DYE_TYPE_OPTIONS } from '../../utils/formulaEval';

const API_BASE = '/api/planning';

const STATUS_CONFIG = {
  PLANNING: { label: 'Perencanaan (Planning)', badge: 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-600/40' },
  QUEUED: { label: 'Antrean (Queued)', badge: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-600/40' },
  WAITING_LA: { label: 'Menunggu LA', badge: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-600/40' },
  RUNNING: { label: 'Sedang Proses (Running)', badge: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-600/40' },
  COMPLETED: { label: 'Selesai (Completed)', badge: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-600/40' },
  HOLD: { label: 'Ditahan (Hold)', badge: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-600/40' }
};

const BatchListView = () => {
  const navigate = useNavigate();
  const { toast, confirm, confirmTwice } = useToast();
  const [batches, setBatches] = useState([]);
  const [machineList, setMachineList] = useState([]);
  const [programList, setProgramList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMachine, setSelectedMachine] = useState('SEMUA');
  const [selectedStatus, setSelectedStatus] = useState('SEMUA');

  // New Batch Modal State - Defaults to DA01 and PT. SMM JETFLOW
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState({
    batch_no: '',
    reference_no: '',
    machine_no: 'DA01',
    program_no: 1,
    recipe_name: 'SCOURING BLEACHING',
    customer: 'PT. SMM JETFLOW',
    article: 'CM 30S RIB 100% Cotton',
    color_code: '1650159',
    color_name: 'UNGU TUA',
    fabric_weight_kg: 350.0,
    liquor_ratio: 8.0,
    fabric_length: 200.0,
    fabric_type: 'COTTON',
    color_shade: 'SEDANG',
    fabric_gsm: 180,
    dye_type: 'REACTIVE',
    chamber_count: 1,
    redye: 0,
    status: 'PLANNING'
  });

  // Transfer Machine Modal State
  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [transferBatch, setTransferBatch] = useState(null);
  const [targetMachine, setTargetMachine] = useState('DA01');

  // FTP Dispatch Batch Modal State
  const [ftpDispatchModalOpen, setFtpDispatchModalOpen] = useState(false);
  const [batchToDispatch, setBatchToDispatch] = useState(null);
  const [dispatchIp, setDispatchIp] = useState('192.168.1.95');
  const [dispatchModel, setDispatchModel] = useState('network_ot');
  const [isDispatching, setIsDispatching] = useState(false);
  const [isSyncingFTP, setIsSyncingFTP] = useState(false);

  // Sync All Batch Folders to FTP Controller (2x Konfirmasi)
  const handleSyncAllBatchFoldersToFTP = async () => {
    const approved = await confirmTwice({
      title1: 'Konfirmasi 1/2 — Sinkronisasi Semua Folder Batch ke FTP',
      message1: 'Sistem akan menyinkronkan seluruh folder batch aktif (BATCHREF.REF & M_xxxx.PRG) ke kontroler FTP.\n\nLanjutkan ke konfirmasi akhir?',
      confirmText1: 'Lanjut ke Konfirmasi Akhir (1/2)',
      title2: '⚠️ KONFIRMASI AKHIR (2/2) — Sinkronisasi FTP',
      message2: 'PERINGATAN: Operasi ini akan menulis folder batch langsung ke kontroler FTP HMI.\n\nApakah Anda YAKIN ingin melanjutkan?',
      confirmText2: 'Ya, Sinkronkan Sekarang',
    });
    if (!approved) return;

    setIsSyncingFTP(true);
    try {
      const res = await axios.post('/api/ftp/sync-all-batch-folders');
      toast.success(res.data.message || 'Sinkronisasi seluruh folder batch ke FTP berhasil!');
      fetchBatches();
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      toast.error('Gagal sinkronisasi folder batch ke FTP: ' + msg);
    } finally {
      setIsSyncingFTP(false);
    }
  };

  // Fetch machines from database
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

  // Fetch programs from /api/programs (exact parity with /programs page)
  const fetchPrograms = async () => {
    try {
      const res = await axios.get('/api/programs/');
      if (res.data && Array.isArray(res.data)) {
        // Sort by program_number ascending
        const sorted = [...res.data].sort((a, b) => (a.program_number || 0) - (b.program_number || 0));
        setProgramList(sorted);
      }
    } catch (err) {
      console.error('Gagal mengambil daftar program:', err);
    }
  };

  // Fetch batches from database
  const fetchBatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/`);
      setBatches(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil data batch dari database:', err);
    } finally {
      setLoading(false);
    }
  };

  // Sync PostgreSQL & SQLite
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

  useEffect(() => {
    fetchBatches();
    fetchMachines();
    fetchPrograms();
  }, []);

  // Compute machine options list with M_95 and DA01 at top
  const machineOptions = React.useMemo(() => {
    const list = ['SEMUA', 'M_95', 'DA01'];
    machineList.forEach(m => {
      if (!list.includes(m.machine_no)) {
        list.push(m.machine_no);
      }
    });
    return list;
  }, [machineList]);

  // Filter batches
  const filteredBatches = batches.filter(b => {
    const matchMach = selectedMachine === 'SEMUA' || b.machine_no === selectedMachine;
    const matchStatus = selectedStatus === 'SEMUA' || b.status === selectedStatus;
    const term = searchTerm.toLowerCase();
    const matchSearch = !searchTerm || 
      (b.batch_no && b.batch_no.toLowerCase().includes(term)) ||
      (b.reference_no && b.reference_no.toLowerCase().includes(term)) ||
      (b.recipe_name && b.recipe_name.toLowerCase().includes(term)) ||
      (b.customer && b.customer.toLowerCase().includes(term)) ||
      (b.article && b.article.toLowerCase().includes(term));
    return matchMach && matchStatus && matchSearch;
  });

  // Handle Create Batch
  const handleCreateBatch = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await axios.post(`${API_BASE}/`, form);
      setIsModalOpen(false);
      fetchBatches();
      toast.success(`Batch ${form.batch_no} berhasil ditambahkan ke antrean!`);
    } catch (err) {
      const msg = err.response?.data?.detail || (typeof err.response?.data === 'string' ? err.response.data : err.message);
      toast.error('Gagal menambahkan batch: ' + msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Status Update
  const handleStatusChange = async (batchId, newStatus) => {
    try {
      await axios.put(`${API_BASE}/${batchId}`, { status: newStatus });
      fetchBatches();
    } catch (err) {
      toast.error('Gagal mengubah status: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Delete
  const handleDeleteBatch = async (batchId) => {
    const ok = await confirm('Apakah Anda yakin ingin menghapus batch ini dari antrean?', {
      title: 'Hapus Batch Produksi',
      confirmText: 'Ya, Hapus',
      danger: true,
    });
    if (!ok) return;
    try {
      await axios.delete(`${API_BASE}/${batchId}`);
      toast.success('Batch berhasil dihapus dari antrean.');
      fetchBatches();
    } catch (err) {
      toast.error('Gagal menghapus batch: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Transfer Machine
  const handleExecuteTransfer = async () => {
    if (!transferBatch) return;
    try {
      await axios.put(`${API_BASE}/${transferBatch.id}`, {
        status: transferBatch.status,
        machine_no: targetMachine,
      });
      fetchBatches();
      setTransferModalOpen(false);
      setTransferBatch(null);
      toast.success(`Batch berhasil dipindahkan ke mesin ${targetMachine} di database!`);
    } catch (err) {
      toast.error('Gagal transfer mesin: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Download Offline Batch ZIP
  const handleDownloadZip = (batchId, refNo, lotNo) => {
    window.open(`${API_BASE}/export-zip/${batchId}`, '_blank');
  };

  // Dispatch Batch Directly to Any HMI Controller via FTP (dengan 2x Popup Konfirmasi)
  const handleExecuteDispatch = async () => {
    if (!batchToDispatch) return;
    const machNo = batchToDispatch.machine_no;
    const targetIp = dispatchIp.trim();

    const approved = await confirmTwice({
      title1: `Konfirmasi 1/2 — Kirim Batch ke HMI ${machNo}`,
      message1: `Batch: ${batchToDispatch.batch_no} (Ref: ${batchToDispatch.reference_no})\nProgram: M_${String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG (${batchToDispatch.recipe_name})\nTarget HMI: Mesin ${machNo} (${targetIp}:21)\n\nPastikan data batch & mesin tujuan sudah benar.`,
      confirmText1: 'Lanjut ke Konfirmasi Akhir (1/2)',
      title2: `⚠️ KONFIRMASI AKHIR (2/2) — Tulis Batch ke HMI ${machNo}`,
      message2: `PERINGATAN: File BATCHREF.REF dan M_${String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG akan ditulis langsung ke kontroler HMI Mesin ${machNo} (${targetIp}).\n\nApakah Anda YAKIN 100% ingin mengirim batch ini sekarang?`,
      confirmText2: `Ya, Kirim ke HMI ${machNo}`,
    });
    if (!approved) return;

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

  // Close open modals on Escape key
  useEffect(() => {
    if (!isModalOpen && !transferModalOpen && !ftpDispatchModalOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setIsModalOpen(false);
        setTransferModalOpen(false);
        setFtpDispatchModalOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isModalOpen, transferModalOpen, ftpDispatchModalOpen]);

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold tracking-tight text-black dark:text-white flex items-center gap-2">
            <Layers className="h-6 w-6 text-primary" />
            Batch
          </h2>
        </div>

        {/* TOP BUTTONS */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-primary hover:bg-opacity-90 text-white text-xs font-semibold px-4 py-2 rounded shadow transition"
          >
            <Plus className="h-4 w-4" />
            Buat Batch Baru
          </button>
          <button
            onClick={() => window.open(`${API_BASE}/export-multi-zip`, '_blank')}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3.5 py-2 rounded shadow transition"
            title="Unduh seluruh antrean batch yang ada sebagai bundle zip OrgaTEX (lengkap dengan QUEUE.BTD dan folder batch)"
          >
            <Download className="h-4 w-4" />
            Unduh Antrean Lengkap (ZIP)
          </button>
          {selectedMachine !== 'SEMUA' && (
            <button
              onClick={() => window.open(`${API_BASE}/export-queue-btd/${selectedMachine}`, '_blank')}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded shadow transition"
              title={`Unduh langsung berkas biner QUEUE.BTD (12.288 byte) untuk mesin ${selectedMachine}`}
            >
              <FileText className="h-4 w-4" />
              Unduh QUEUE.BTD ({selectedMachine})
            </button>
          )}
          <button
            onClick={() => navigate('/ftp')}
            className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 dark:bg-[#24303f] dark:hover:bg-[#2d3a4d] border border-stroke dark:border-gray-700 text-gray-700 dark:text-gray-200 text-xs px-3.5 py-2 rounded shadow-xs transition"
          >
            <Send className="h-4 w-4 text-emerald-500 dark:text-emerald-400" />
            Buka FTP Explorer
          </button>
          <button
            onClick={handleSyncAllBatchFoldersToFTP}
            disabled={isSyncingFTP}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3.5 py-2 rounded shadow-xs transition"
            title="Sinkronkan seluruh nomor batch_ref_no sebagai folder baru di ftp://192.168.1.95/Network/F/OT/BATCH/<batch_ref_no>/"
          >
            <RefreshCw className={`h-4 w-4 ${isSyncingFTP ? 'animate-spin' : ''}`} />
            {isSyncingFTP ? 'Syncing FTP...' : 'Sync Batch ke FTP (192.168.1.95)'}
          </button>
          <button
            onClick={handleSyncDB}
            disabled={syncing}
            className="flex items-center gap-1.5 bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/40 dark:hover:bg-blue-800/60 border border-blue-200 dark:border-blue-600/50 text-blue-700 dark:text-blue-300 text-xs px-3 py-2 rounded shadow-xs transition"
            title="Sinkronkan data antara PostgreSQL pt_smm_jetflow dan SQLite lokal"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin text-blue-600 dark:text-blue-400' : 'text-blue-600 dark:text-blue-400'}`} />
            {syncing ? 'Syncing...' : 'Sync DB'}
          </button>
          <button
            onClick={fetchBatches}
            disabled={loading}
            className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-[#24303f] dark:hover:bg-[#2d3a4d] border border-stroke dark:border-gray-700 text-gray-700 dark:text-gray-300 text-xs px-3 py-2 rounded shadow-xs transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-primary' : ''}`} />
          </button>
        </div>
      </div>

      {/* FILTER & SEARCH BAR */}
      <div className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg p-3.5 shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
          {/* Search box */}
          <div className="sm:col-span-5 relative">
            <Search className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Cari No Lot, Referensi, Resep, Customer, atau Kain..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-gray-50 dark:bg-meta-4 border border-stroke dark:border-strokedark text-black dark:text-white text-xs rounded pl-9 pr-3 py-2 outline-none focus:border-primary"
            />
          </div>

          {/* Machine Filter */}
          <div className="sm:col-span-3 flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">Mesin:</span>
            <select
              value={selectedMachine}
              onChange={(e) => setSelectedMachine(e.target.value)}
              className="w-full bg-gray-50 dark:bg-meta-4 border border-stroke dark:border-strokedark text-black dark:text-white text-xs rounded px-2.5 py-2 outline-none font-mono"
            >
              {machineOptions.map(m => (
                <option key={m} value={m} className="bg-white dark:bg-boxdark text-black dark:text-white">{m}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="sm:col-span-4 flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full bg-gray-50 dark:bg-meta-4 border border-stroke dark:border-strokedark text-black dark:text-white text-xs rounded px-2.5 py-2 outline-none font-mono"
            >
              <option value="SEMUA" className="bg-white dark:bg-boxdark text-black dark:text-white">SEMUA STATUS</option>
              <option value="PLANNING" className="bg-white dark:bg-boxdark text-black dark:text-white">Perencanaan (Planning)</option>
              <option value="QUEUED" className="bg-white dark:bg-boxdark text-black dark:text-white">Antrean (Queued)</option>
              <option value="WAITING_LA" className="bg-white dark:bg-boxdark text-black dark:text-white">Menunggu LA</option>
              <option value="RUNNING" className="bg-white dark:bg-boxdark text-black dark:text-white">Sedang Proses (Running)</option>
              <option value="COMPLETED" className="bg-white dark:bg-boxdark text-black dark:text-white">Selesai (Completed)</option>
              <option value="HOLD" className="bg-white dark:bg-boxdark text-black dark:text-white">Ditahan (Hold)</option>
            </select>
          </div>
        </div>
      </div>

      {/* BATCH TABLE */}
      <div className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-100 dark:bg-meta-4 text-[11px] uppercase tracking-wider text-gray-600 dark:text-gray-400 font-semibold border-b border-stroke dark:border-strokedark">
              <tr>
                <th className="py-2.5 px-3 w-10 text-center">Pos</th>
                <th className="py-2.5 px-3 w-28">Ref / Lot No</th>
                <th className="py-2.5 px-3 w-16 text-center">Mesin</th>
                <th className="py-2.5 px-3">Program & Resep Formula</th>
                <th className="py-2.5 px-3">Customer / Artikel Kain</th>
                <th className="py-2.5 px-3 text-right">Berat / Air</th>
                <th className="py-2.5 px-3 w-32 text-center">Status</th>
                <th className="py-2.5 px-3 w-40 text-center">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke dark:divide-strokedark text-xs">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-500 dark:text-gray-400">
                    <RefreshCw className="h-6 w-6 animate-spin text-primary mx-auto mb-2" />
                    Memuat antrean batch produksi...
                  </td>
                </tr>
              ) : filteredBatches.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-500">
                    Tidak ada batch yang cocok dengan kriteria filter saat ini.
                  </td>
                </tr>
              ) : (
                filteredBatches.map((b, idx) => {
                  const statusInfo = STATUS_CONFIG[b.status] || { label: b.status, badge: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300' };
                  return (
                    <tr key={b.id} className="hover:bg-gray-50 dark:hover:bg-meta-4/40 transition group">
                      {/* Posisi */}
                      <td className="py-2.5 px-3 text-center font-bold text-gray-500 dark:text-gray-400 font-mono">
                        {b.position || idx + 1}
                      </td>

                      {/* Ref & Lot */}
                      <td className="py-2.5 px-3">
                        <div className="font-mono font-bold text-black dark:text-white flex items-center gap-1.5">
                          <span className="text-amber-600 dark:text-amber-400">{b.batch_no}</span>
                        </div>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 font-mono block">
                          Ref: {b.reference_no}
                        </span>
                      </td>

                      {/* Mesin */}
                      <td className="py-2.5 px-3 text-center">
                        <span className="bg-primary/10 border border-primary/20 text-primary font-bold font-mono px-2 py-0.5 rounded text-[11px]">
                          {b.machine_no}
                        </span>
                      </td>

                      {/* Program & Resep */}
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-1.5">
                          <FileCode className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                          <span>M_{String(b.program_no || 1).padStart(4, '0')}.PRG</span>
                          <span className="text-gray-500 dark:text-gray-400 font-normal">| {b.recipe_name}</span>
                        </div>
                        <span className="text-[11px] text-gray-500 dark:text-gray-400 block mt-0.5">
                          Warna: <span className="text-gray-700 dark:text-gray-300 font-medium">{b.color_name}</span> ({b.color_code})
                        </span>
                      </td>

                      {/* Customer / Artikel */}
                      <td className="py-2.5 px-3">
                        <span className="text-black dark:text-white font-medium block">{b.customer}</span>
                        <span className="text-[11px] text-gray-500 dark:text-gray-400 block">{b.article}</span>
                      </td>

                      {/* Berat & Air */}
                      <td className="py-2.5 px-3 text-right font-mono">
                        <span className="text-black dark:text-white font-bold">{b.fabric_weight_kg} kg</span>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 block">
                          LR 1:{b.liquor_ratio} ({b.total_water_l || Math.round(b.fabric_weight_kg * b.liquor_ratio)} L)
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-2.5 px-3 text-center">
                        <select
                          value={b.status}
                          onChange={(e) => handleStatusChange(b.id, e.target.value)}
                          className={`text-[10px] font-mono font-semibold px-2 py-1 rounded border outline-none cursor-pointer ${statusInfo.badge}`}
                        >
                          <option value="PLANNING" className="bg-white dark:bg-boxdark text-purple-600 dark:text-purple-300">PLANNING</option>
                          <option value="QUEUED" className="bg-white dark:bg-boxdark text-amber-600 dark:text-amber-300">QUEUED</option>
                          <option value="WAITING_LA" className="bg-white dark:bg-boxdark text-blue-600 dark:text-blue-300">WAITING LA</option>
                          <option value="RUNNING" className="bg-white dark:bg-boxdark text-emerald-600 dark:text-emerald-300">RUNNING</option>
                          <option value="COMPLETED" className="bg-white dark:bg-boxdark text-slate-600 dark:text-slate-300">COMPLETED</option>
                          <option value="HOLD" className="bg-white dark:bg-boxdark text-rose-600 dark:text-rose-300">HOLD</option>
                        </select>
                      </td>

                      {/* Aksi */}
                      <td className="py-2.5 px-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {/* Send via FTP (Semua Mesin HMI — dengan 2x Konfirmasi) */}
                          <button
                            onClick={() => {
                              const mObj = machineList.find(m => m.machine_no === b.machine_no);
                              setBatchToDispatch(b);
                              setDispatchIp(mObj?.ip_address || (b.machine_no === 'DA01' || b.machine_no === 'M_95' ? '192.168.1.95' : '172.16.110.100'));
                              setDispatchModel(
                                b.machine_no === 'DA01' || b.machine_no === 'M_95' || (mObj?.controller_type || '').includes('797')
                                  ? 'network_ot'
                                  : 'network_ot'
                              );
                              setFtpDispatchModalOpen(true);
                            }}
                            className="p-1.5 text-gray-500 hover:text-emerald-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-emerald-400 dark:hover:bg-meta-4 rounded transition"
                            title={`Kirim Batch ke HMI Mesin ${b.machine_no} via FTP (2x Konfirmasi)`}
                          >
                            <Send className="h-4 w-4" />
                          </button>

                          {/* Download ZIP */}
                          <button
                            onClick={() => handleDownloadZip(b.id, b.reference_no, b.batch_no)}
                            className="p-1.5 text-gray-500 hover:text-primary hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-meta-4 rounded transition"
                            title="Unduh Paket ZIP OrgaTEX"
                          >
                            <Download className="h-4 w-4" />
                          </button>

                          {/* Transfer Machine */}
                          <button
                            onClick={() => {
                              setTransferBatch(b);
                              setTransferModalOpen(true);
                            }}
                            className="p-1.5 text-gray-500 hover:text-amber-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-amber-400 dark:hover:bg-meta-4 rounded transition"
                            title="Pindah Mesin (Transfer)"
                          >
                            <Cpu className="h-4 w-4" />
                          </button>

                          {/* Delete */}
                          <button
                            onClick={() => handleDeleteBatch(b.id)}
                            className="p-1.5 text-gray-500 hover:text-rose-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-rose-400 dark:hover:bg-meta-4 rounded transition"
                            title="Hapus Batch"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL: BUAT BATCH BARU */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Tambah Batch Produksi Baru"
          onClick={() => setIsModalOpen(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Tambah Batch Produksi Baru
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-black dark:hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateBatch} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Nomor Lot / Batch:</label>
                  <input
                    type="text"
                    required
                    placeholder="misal PJT030"
                    value={form.batch_no}
                    onChange={(e) => setForm({ ...form, batch_no: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Target Mesin Celup:</label>
                  <select
                    value={form.machine_no}
                    onChange={(e) => setForm({ ...form, machine_no: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono outline-none focus:border-primary font-bold"
                  >
                    <optgroup label="⭐ SETEX 797CE Controllers (Prioritas)">
                      <option value="M_95">M_95 - SETEX 797CE Mesin DA01 (192.168.1.95)</option>
                      <option value="DA01">DA01 - SETEX 797CE Mesin DA01 (192.168.1.95)</option>
                    </optgroup>
                    {machineList.filter(m => m.machine_no !== 'M_95' && m.machine_no !== 'DA01').length > 0 && (
                      <optgroup label="SECOM 777 / Novatech Mesin Produksi">
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
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">
                    Program Secom (Dari Database /programs):
                  </label>
                  <div className="flex gap-1.5">
                    <input
                      type="number"
                      value={form.program_no}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10) || 1;
                        const match = programList.find(p => (p.program_number || p.program_no) === val);
                        setForm({
                          ...form,
                          program_no: val,
                          ...(match ? { recipe_name: match.program_name || match.name } : {})
                        });
                      }}
                      className="w-20 bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2 py-2 rounded font-mono outline-none focus:border-primary font-bold text-center"
                      title="Nomor Program Secom M_xxxx"
                    />
                    <select
                      value={form.program_no}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10) || 1;
                        const match = programList.find(p => (p.program_number || p.program_no) === val);
                        setForm({
                          ...form,
                          program_no: val,
                          ...(match ? { recipe_name: match.program_name || match.name } : {})
                        });
                      }}
                      className="flex-1 bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2 py-2 rounded font-mono text-xs outline-none focus:border-primary"
                    >
                      {/* Priority: Mesin Terpilih (DA01 / M_95) */}
                      {programList.filter(p => {
                        const isDaMatch = (form.machine_no === 'M_95' || form.machine_no === 'DA01') && (p.machine_code === 'DA01' || p.machine_code === 'M_95');
                        const isMachMatch = p.machine_code === form.machine_no;
                        return isDaMatch || isMachMatch;
                      }).length > 0 && (
                        <optgroup label={`⭐ Program Mesin ${form.machine_no} (${form.machine_no === 'M_95' || form.machine_no === 'DA01' ? 'DA01 / 797CE' : form.machine_no})`}>
                          {programList
                            .filter(p => {
                              const isDaMatch = (form.machine_no === 'M_95' || form.machine_no === 'DA01') && (p.machine_code === 'DA01' || p.machine_code === 'M_95');
                              return isDaMatch || p.machine_code === form.machine_no;
                            })
                            .map(p => {
                              const pNo = p.program_number || p.program_no;
                              const pName = p.program_name || p.name || 'Program';
                              return (
                                <option key={`mach-${pNo}`} value={pNo}>
                                  M_{String(pNo).padStart(4, '0')}.PRG - {pName} ({p.total_steps || 0} Step)
                                </option>
                              );
                            })}
                        </optgroup>
                      )}

                      {/* Katalog Program Mesin Lainnya */}
                      <optgroup label="Daftar Program Mesin Lainnya / Katalog OrgaTEX">
                        {programList
                          .filter(p => {
                            const isDaMatch = (form.machine_no === 'M_95' || form.machine_no === 'DA01') && (p.machine_code === 'DA01' || p.machine_code === 'M_95');
                            return !(isDaMatch || p.machine_code === form.machine_no);
                          })
                          .map(p => {
                            const pNo = p.program_number || p.program_no;
                            const pName = p.program_name || p.name || 'Program';
                            return (
                              <option key={`other-${pNo}`} value={pNo}>
                                M_{String(pNo).padStart(4, '0')}.PRG - {pName} ({p.machine_code || 'SETEX'} · {p.total_steps || 0} Step)
                              </option>
                            );
                          })}
                      </optgroup>

                      {/* Fallback jika program_no belum ada di list */}
                      {!programList.some(p => (p.program_number || p.program_no) === form.program_no) && (
                        <option value={form.program_no}>Custom Prog #{form.program_no}</option>
                      )}
                    </select>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Nama Resep Formula:</label>
                  <input
                    type="text"
                    value={form.recipe_name}
                    onChange={(e) => setForm({ ...form, recipe_name: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Nama Customer:</label>
                  <input
                    type="text"
                    value={form.customer}
                    onChange={(e) => setForm({ ...form, customer: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Artikel Kain:</label>
                  <input
                    type="text"
                    value={form.article}
                    onChange={(e) => setForm({ ...form, article: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Kode Warna:</label>
                  <input
                    type="text"
                    value={form.color_code}
                    onChange={(e) => setForm({ ...form, color_code: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Nama Warna:</label>
                  <input
                    type="text"
                    value={form.color_name}
                    onChange={(e) => setForm({ ...form, color_name: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-gray-50 dark:bg-meta-4 p-3 rounded border border-stroke dark:border-strokedark">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Berat Kain (kg):</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.fabric_weight_kg}
                    onChange={(e) => setForm({ ...form, fabric_weight_kg: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Liquor Ratio (1:x):</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form.liquor_ratio}
                    onChange={(e) => setForm({ ...form, liquor_ratio: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Total Air Dihitung (L):</label>
                  <input
                    type="text"
                    disabled
                    value={`${(form.fabric_weight_kg * form.liquor_ratio).toFixed(1)} Liter`}
                    className="w-full bg-gray-100 dark:bg-slate-800 border border-stroke dark:border-gray-700 text-emerald-600 dark:text-emerald-400 font-bold px-3 py-2 rounded font-mono"
                  />
                </div>
              </div>

              {/* PARAMETER KAIN & PROSES (UNTUK FORMULA OTOMATIS) */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-indigo-50/40 dark:bg-indigo-950/15 p-3 rounded border border-indigo-200/70 dark:border-indigo-800/40">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Jenis Kain / Serat:</label>
                  <select
                    value={form.fabric_type}
                    onChange={(e) => setForm({ ...form, fabric_type: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-2 rounded font-bold outline-none focus:border-primary"
                  >
                    {FABRIC_TYPE_OPTIONS.map((ft) => (
                      <option key={ft} value={ft}>{ft}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Kedalaman Warna (Shade):</label>
                  <select
                    value={form.color_shade}
                    onChange={(e) => setForm({ ...form, color_shade: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-2 rounded font-bold outline-none focus:border-primary"
                  >
                    {COLOR_SHADE_OPTIONS.map((sh) => (
                      <option key={sh} value={sh}>{sh}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Jenis Zat Warna:</label>
                  <select
                    value={form.dye_type}
                    onChange={(e) => setForm({ ...form, dye_type: e.target.value })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-2 rounded outline-none focus:border-primary"
                  >
                    {DYE_TYPE_OPTIONS.map((dt) => (
                      <option key={dt} value={dt}>{dt}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Gramasi Kain (GSM):</label>
                  <input
                    type="number"
                    step="1"
                    value={form.fabric_gsm}
                    onChange={(e) => setForm({ ...form, fabric_gsm: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-1.5 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Panjang Kain (m):</label>
                  <input
                    type="number"
                    step="1"
                    value={form.fabric_length}
                    onChange={(e) => setForm({ ...form, fabric_length: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-1.5 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Status Proses:</label>
                  <select
                    value={form.redye}
                    onChange={(e) => setForm({ ...form, redye: parseInt(e.target.value, 10) || 0 })}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-2.5 py-1.5 rounded outline-none focus:border-primary"
                  >
                    <option value={0}>Normal (0)</option>
                    <option value={1}>Redye / Celup Ulang (1)</option>
                  </select>
                </div>
              </div>

              {/* LIVE PREVIEW PARAMETER FORMULA */}
              <BatchFormulaPreview form={form} />

              <div>
                <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Tahap Masuk Awal (Status):</label>
                <select
                  value={form.status || 'PLANNING'}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono outline-none focus:border-primary font-bold"
                >
                  <option value="PLANNING">Perencanaan (PLANNING) - Disimpan di database (Belum dikirim ke HMI)</option>
                  <option value="QUEUED">Antrean Produksi (QUEUED) - Masuk antrean aktif mesin</option>
                </select>
                <span className="text-[10px] text-gray-500 dark:text-gray-400 block mt-1">
                  Batch berstatus "Perencanaan" belum akan dikirim ke mesin HMI sampai Anda memindahkannya ke antrean (QUEUED).
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-meta-4 dark:hover:bg-meta-4/80 dark:text-white px-4 py-2 rounded border border-stroke dark:border-strokedark transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="bg-primary hover:bg-opacity-90 disabled:opacity-50 text-white font-semibold px-5 py-2 rounded flex items-center gap-1.5 transition"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Menyimpan...
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" />
                      Simpan Batch
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: TRANSFER MESIN (DlgMachineBatchTransfer) */}
      {transferModalOpen && transferBatch && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Pindah Alokasi Mesin"
          onClick={() => setTransferModalOpen(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg w-full max-w-md p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                <Cpu className="h-5 w-5 text-amber-500" />
                Pindah Alokasi Mesin (Batch Transfer)
              </h3>
              <button onClick={() => setTransferModalOpen(false)} className="text-gray-400 hover:text-black dark:hover:text-white">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-gray-600 dark:text-gray-300">
                Pindahkan batch <span className="font-bold text-black dark:text-white">{transferBatch.batch_no}</span> (Ref: {transferBatch.reference_no}) dari mesin <span className="text-rose-500 font-bold">{transferBatch.machine_no}</span> ke mesin tujuan:
              </p>

              <div>
                <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Mesin Tujuan Baru:</label>
                <select
                  value={targetMachine}
                  onChange={(e) => setTargetMachine(e.target.value)}
                  className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-white px-3 py-2 rounded font-mono outline-none"
                >
                  <optgroup label="⭐ SETEX 797CE">
                    {['M_95', 'DA01'].filter(m => m !== transferBatch.machine_no).map(m => (
                      <option key={m} value={m}>{m} - SETEX 797CE (192.168.1.95)</option>
                    ))}
                  </optgroup>
                  <optgroup label="Mesin Produksi Lainnya">
                    {machineList
                      .filter(m => m.machine_no !== 'M_95' && m.machine_no !== 'DA01' && m.machine_no !== transferBatch.machine_no)
                      .map(m => (
                        <option key={m.machine_no} value={m.machine_no}>
                          {m.machine_no} - {m.display_name} ({m.ip_address})
                        </option>
                      ))}
                  </optgroup>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setTransferModalOpen(false)}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-meta-4 dark:hover:bg-meta-4/80 dark:text-white px-3 py-1.5 rounded border border-stroke dark:border-strokedark transition"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleExecuteTransfer}
                  className="bg-amber-600 hover:bg-amber-500 text-white font-semibold px-4 py-1.5 rounded transition"
                >
                  Pindahkan Sekarang
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* MODAL: FTP DISPATCH BATCH DIRECT TO CONTROLLER */}
      {ftpDispatchModalOpen && batchToDispatch && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Kirim Batch ke Kontroler FTP"
          onClick={() => setFtpDispatchModalOpen(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4 text-xs"
          >
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                <Send className="h-5 w-5 text-emerald-500" />
                Kirim Batch ke Kontroler FTP (SETEX 797CE / 777)
              </h3>
              <button
                onClick={() => setFtpDispatchModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div className="bg-gray-50 dark:bg-meta-4 p-3 rounded border border-stroke dark:border-strokedark space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Batch Target:</span>
                  <strong className="text-black dark:text-white">#{batchToDispatch.batch_no} (Ref: {batchToDispatch.reference_no})</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Resep / Formula:</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{batchToDispatch.recipe_name || 'Standard'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Nomor Program:</span>
                  <span className="text-amber-600 dark:text-amber-400 font-semibold">M_{String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 bg-gray-50 dark:bg-meta-4 p-3 rounded border border-stroke dark:border-strokedark">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">IP Kontroler Target:</label>
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
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-emerald-400 font-mono font-bold rounded px-2.5 py-1.5 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 block mt-1">Default: 192.168.1.95</span>
                </div>

                <div>
                  <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">Tipe Kontroler / Folder:</label>
                  <select
                    value={dispatchModel}
                    onChange={(e) => setDispatchModel(e.target.value)}
                    className="w-full bg-white dark:bg-slate-900 border border-stroke dark:border-gray-700 text-black dark:text-amber-300 font-bold rounded px-2.5 py-1.5 outline-none"
                  >
                    <option value="network_ot">OrgaTEX Share (/Network/F/OT/BATCH/ + QUEUE.BTD)</option>
                    <option value="797">SETEX 797CE Lokal (/Flashdisk/SC797CE/BATCH)</option>
                    <option value="777">SETEX 777 Lokal (/Storage/sc777ce/BATCH)</option>
                  </select>
                  <span className="text-[10px] text-gray-400 block mt-1">Auto-fallback aktif jika folder belum ada</span>
                </div>
              </div>

              <div className="text-[11px] text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-meta-4/60 p-2.5 rounded border border-stroke dark:border-strokedark space-y-1.5">
                <span className="font-bold text-gray-700 dark:text-gray-300">File biner yang langsung diunggah:</span>
                <ul className="list-disc list-inside text-gray-600 dark:text-slate-300 space-y-0.5">
                  <li>Folder Batch: <code className="text-emerald-600 dark:text-emerald-400 font-mono">
                    {dispatchModel === 'network_ot'
                      ? `/Network/F/OT/BATCH/${batchToDispatch.reference_no}/`
                      : (dispatchModel === '797' ? '/Flashdisk/SC797CE/BATCH/' : '/Storage/sc777ce/BATCH/')}
                  </code></li>
                  <li className="pl-4 text-gray-500 dark:text-gray-400">- <code className="text-emerald-600 dark:text-emerald-300">BATCHREF.REF</code> (762-byte Secom binary)</li>
                  <li className="pl-4 text-gray-500 dark:text-gray-400">- <code className="text-emerald-600 dark:text-emerald-300">M_{String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG</code> (Biner program mikro)</li>
                  {dispatchModel === 'network_ot' && (
                    <li>Replace Antrean: <code className="text-cyan-600 dark:text-cyan-400 font-mono">
                      /Network/F/OT/MACHINES/{batchToDispatch.machine_no}/BATCHES/QUEUE.BTD
                    </code></li>
                  )}
                </ul>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setFtpDispatchModalOpen(false)}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-meta-4 dark:hover:bg-meta-4/80 dark:text-white px-3 py-1.5 rounded border border-stroke dark:border-strokedark transition"
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

export default BatchListView;
