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
  Cpu, 
  ExternalLink 
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const API_BASE = '/api/planning';

const STATUS_CONFIG = {
  QUEUED: { label: 'Antrean (Queued)', badge: 'bg-amber-950/40 text-amber-300 border-amber-600/40' },
  WAITING_LA: { label: 'Menunggu LA', badge: 'bg-blue-950/40 text-blue-300 border-blue-600/40' },
  RUNNING: { label: 'Sedang Proses (Running)', badge: 'bg-emerald-950/40 text-emerald-300 border-emerald-600/40' },
  COMPLETED: { label: 'Selesai (Completed)', badge: 'bg-slate-800 text-slate-300 border-slate-600/40' },
  HOLD: { label: 'Ditahan (Hold)', badge: 'bg-rose-950/40 text-rose-300 border-rose-600/40' }
};

const MACHINE_OPTIONS = ['SEMUA', 'DA01', '10B', 'TD12', 'TD13', 'B012', 'E013', 'M01'];

const BatchListView = () => {
  const navigate = useNavigate();
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMachine, setSelectedMachine] = useState('SEMUA');
  const [selectedStatus, setSelectedStatus] = useState('SEMUA');

  // New Batch Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState({
    batch_no: '',
    reference_no: '',
    machine_no: 'TD12',
    program_no: 401,
    recipe_name: 'Reactive Dyeing Standard Formula',
    customer: 'PT. ARTA PERMAI',
    article: 'CM 30S RIB 100% Cotton',
    color_code: '1650159',
    color_name: 'UNGU TUA',
    fabric_weight_kg: 350.0,
    liquor_ratio: 8.0,
  });

  // Transfer Machine Modal State
  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [transferBatch, setTransferBatch] = useState(null);
  const [targetMachine, setTargetMachine] = useState('TD13');

  // FTP Dispatch Batch Modal State
  const [ftpDispatchModalOpen, setFtpDispatchModalOpen] = useState(false);
  const [batchToDispatch, setBatchToDispatch] = useState(null);
  const [dispatchIp, setDispatchIp] = useState('192.168.1.95');
  const [dispatchModel, setDispatchModel] = useState('797');
  const [isDispatching, setIsDispatching] = useState(false);

  // Fetch batches
  const fetchBatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get(API_BASE);
      setBatches(res.data || []);
    } catch (err) {
      console.error('Gagal mengambil data batch:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

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
    try {
      await axios.post(API_BASE, form);
      setIsModalOpen(false);
      fetchBatches();
      alert(`Batch ${form.batch_no} berhasil ditambahkan ke antrean!`);
    } catch (err) {
      alert('Gagal menambahkan batch: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Status Update
  const handleStatusChange = async (batchId, newStatus) => {
    try {
      await axios.put(`${API_BASE}/${batchId}`, { status: newStatus });
      fetchBatches();
    } catch (err) {
      alert('Gagal mengubah status: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Delete
  const handleDeleteBatch = async (batchId) => {
    if (!window.confirm('Apakah Anda yakin ingin menghapus batch ini dari antrean?')) return;
    try {
      await axios.delete(`${API_BASE}/${batchId}`);
      fetchBatches();
    } catch (err) {
      alert('Gagal menghapus batch: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Transfer Machine
  const handleExecuteTransfer = async () => {
    if (!transferBatch) return;
    try {
      // Create duplicate or reassign
      await axios.put(`${API_BASE}/${transferBatch.id}`, {
        status: transferBatch.status,
      });
      // In local mode, update batch object machine
      const updated = batches.map(b => b.id === transferBatch.id ? { ...b, machine_no: targetMachine } : b);
      setBatches(updated);
      setTransferModalOpen(false);
      setTransferBatch(null);
      alert(`Batch berhasil dipindahkan ke mesin ${targetMachine}!`);
    } catch (err) {
      alert('Gagal transfer mesin: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Download Offline Batch ZIP
  const handleDownloadZip = (batchId, refNo, lotNo) => {
    window.open(`${API_BASE}/export-zip/${batchId}`, '_blank');
  };

  // Dispatch Batch Directly to Controller via FTP
  const handleExecuteDispatch = async () => {
    if (!batchToDispatch) return;
    setIsDispatching(true);
    try {
      const is797 = dispatchModel === '797' || dispatchIp.trim() === '192.168.1.95';
      const targetDir = is797 ? '/Flashdisk/SC797CE/BATCH' : '/Storage/sc777ce/BATCH';
      const res = await axios.post('/api/ftp/dispatch-batch', {
        ip: dispatchIp.trim(),
        port: 21,
        batch_id: batchToDispatch.id,
        controller_type: is797 ? '797' : '777',
        target_dir: targetDir
      });
      alert(res.data.message || `Batch ${batchToDispatch.batch_no} berhasil dikirim ke Kontroler FTP!`);
      setFtpDispatchModalOpen(false);
      fetchBatches();
    } catch (err) {
      alert('Gagal mengirim batch via FTP: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsDispatching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Layers className="h-7 w-7 text-primary" />
              Batch Pool & Antrean Produksi (SCX620)
            </h2>
            <span className="text-[11px] bg-primary/20 text-primary border border-primary/40 px-2 py-0.5 rounded font-mono font-semibold">
              OrgaTEX Parity
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Daftar lengkap alokasi batch, nomor resep, formula celup, dan status antrean mikrokontroler
          </p>
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
          <button
            onClick={() => navigate('/ftp')}
            className="flex items-center gap-2 bg-[#24303f] hover:bg-[#2d3a4d] border border-gray-700 text-gray-200 text-xs px-3.5 py-2 rounded shadow transition"
          >
            <Send className="h-4 w-4 text-emerald-400" />
            Buka FTP Explorer
          </button>
          <button
            onClick={fetchBatches}
            disabled={loading}
            className="flex items-center gap-1.5 bg-[#24303f] hover:bg-[#2d3a4d] border border-gray-700 text-gray-300 text-xs px-3 py-2 rounded shadow transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-primary' : ''}`} />
          </button>
        </div>
      </div>

      {/* FILTER & SEARCH BAR */}
      <div className="bg-[#1c2434] border border-gray-700/60 rounded-lg p-3.5 shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
          {/* Search box */}
          <div className="sm:col-span-5 relative">
            <Search className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Cari No Lot, Referensi, Resep, Customer, atau Kain..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#24303f] border border-gray-700 text-white text-xs rounded pl-9 pr-3 py-2 outline-none focus:border-primary"
            />
          </div>

          {/* Machine Filter */}
          <div className="sm:col-span-3 flex items-center gap-2">
            <span className="text-xs text-gray-400 whitespace-nowrap">Mesin:</span>
            <select
              value={selectedMachine}
              onChange={(e) => setSelectedMachine(e.target.value)}
              className="w-full bg-[#24303f] border border-gray-700 text-white text-xs rounded px-2.5 py-2 outline-none font-mono"
            >
              {MACHINE_OPTIONS.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="sm:col-span-4 flex items-center gap-2">
            <span className="text-xs text-gray-400 whitespace-nowrap">Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full bg-[#24303f] border border-gray-700 text-white text-xs rounded px-2.5 py-2 outline-none font-mono"
            >
              <option value="SEMUA">SEMUA STATUS</option>
              <option value="QUEUED">Antrean (Queued)</option>
              <option value="WAITING_LA">Menunggu LA</option>
              <option value="RUNNING">Sedang Proses (Running)</option>
              <option value="COMPLETED">Selesai (Completed)</option>
              <option value="HOLD">Ditahan (Hold)</option>
            </select>
          </div>
        </div>
      </div>

      {/* BATCH TABLE */}
      <div className="bg-[#1c2434] border border-gray-700/60 rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-[#24303f] text-[11px] uppercase tracking-wider text-gray-400 font-semibold border-b border-gray-700">
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
            <tbody className="divide-y divide-gray-800 text-xs">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-400">
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
                  const statusInfo = STATUS_CONFIG[b.status] || { label: b.status, badge: 'bg-gray-800 text-gray-300' };
                  return (
                    <tr key={b.id} className="hover:bg-[#24303f]/50 transition group">
                      {/* Posisi */}
                      <td className="py-2.5 px-3 text-center font-bold text-gray-400 font-mono">
                        {b.position || idx + 1}
                      </td>

                      {/* Ref & Lot */}
                      <td className="py-2.5 px-3">
                        <div className="font-mono font-bold text-white flex items-center gap-1.5">
                          <span className="text-amber-400">{b.batch_no}</span>
                        </div>
                        <span className="text-[10px] text-gray-400 font-mono block">
                          Ref: {b.reference_no}
                        </span>
                      </td>

                      {/* Mesin */}
                      <td className="py-2.5 px-3 text-center">
                        <span className="bg-[#24303f] border border-gray-700 text-primary font-bold font-mono px-2 py-0.5 rounded text-[11px]">
                          {b.machine_no}
                        </span>
                      </td>

                      {/* Program & Resep */}
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-gray-100 flex items-center gap-1.5">
                          <FileCode className="h-3.5 w-3.5 text-emerald-400" />
                          <span>M_{String(b.program_no || 1).padStart(4, '0')}.PRG</span>
                          <span className="text-gray-400 font-normal">| {b.recipe_name}</span>
                        </div>
                        <span className="text-[11px] text-gray-400 block mt-0.5">
                          Warna: <span className="text-gray-300 font-medium">{b.color_name}</span> ({b.color_code})
                        </span>
                      </td>

                      {/* Customer / Artikel */}
                      <td className="py-2.5 px-3">
                        <span className="text-white font-medium block">{b.customer}</span>
                        <span className="text-[11px] text-gray-400 block">{b.article}</span>
                      </td>

                      {/* Berat & Air */}
                      <td className="py-2.5 px-3 text-right font-mono">
                        <span className="text-white font-bold">{b.fabric_weight_kg} kg</span>
                        <span className="text-[10px] text-gray-400 block">
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
                          <option value="QUEUED" className="bg-[#1c2434] text-amber-300">QUEUED</option>
                          <option value="WAITING_LA" className="bg-[#1c2434] text-blue-300">WAITING LA</option>
                          <option value="RUNNING" className="bg-[#1c2434] text-emerald-300">RUNNING</option>
                          <option value="COMPLETED" className="bg-[#1c2434] text-slate-300">COMPLETED</option>
                          <option value="HOLD" className="bg-[#1c2434] text-rose-300">HOLD</option>
                        </select>
                      </td>

                      {/* Aksi */}
                      <td className="py-2.5 px-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {/* Send via FTP */}
                          <button
                            onClick={() => {
                              setBatchToDispatch(b);
                              const is797Target = b.machine_no === '797' || b.machine_no?.includes('797');
                              if (is797Target) {
                                setDispatchIp('192.168.1.95');
                                setDispatchModel('797');
                              } else if (b.machine_no === '10B') {
                                setDispatchIp('172.16.110.160');
                                setDispatchModel('777');
                              } else {
                                setDispatchIp('192.168.1.95');
                                setDispatchModel('797');
                              }
                              setFtpDispatchModalOpen(true);
                            }}
                            className="p-1.5 text-gray-300 hover:text-emerald-400 hover:bg-[#24303f] rounded transition"
                            title="Kirim ke Controller via FTP (Port 21)"
                          >
                            <Send className="h-4 w-4" />
                          </button>

                          {/* Download ZIP */}
                          <button
                            onClick={() => handleDownloadZip(b.id, b.reference_no, b.batch_no)}
                            className="p-1.5 text-gray-300 hover:text-primary hover:bg-[#24303f] rounded transition"
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
                            className="p-1.5 text-gray-300 hover:text-amber-400 hover:bg-[#24303f] rounded transition"
                            title="Pindah Mesin (Transfer)"
                          >
                            <Cpu className="h-4 w-4" />
                          </button>

                          {/* Delete */}
                          <button
                            onClick={() => handleDeleteBatch(b.id)}
                            className="p-1.5 text-gray-300 hover:text-rose-400 hover:bg-[#24303f] rounded transition"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-700 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Tambah Batch Produksi Baru (OrgaTEX SCX620)
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateBatch} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Nomor Lot / Batch:</label>
                  <input
                    type="text"
                    required
                    placeholder="misal PJT030"
                    value={form.batch_no}
                    onChange={(e) => setForm({ ...form, batch_no: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Target Mesin Celup:</label>
                  <select
                    value={form.machine_no}
                    onChange={(e) => setForm({ ...form, machine_no: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  >
                    <option value="TD12">TD12 (172.16.110.101)</option>
                    <option value="TD13">TD13 (172.16.110.102)</option>
                    <option value="B012">B012 (Thies SoftTRD)</option>
                    <option value="E013">E013 (Sclavos Athena)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Nomor Program Secom:</label>
                  <input
                    type="number"
                    value={form.program_no}
                    onChange={(e) => setForm({ ...form, program_no: parseInt(e.target.value, 10) || 1 })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Nama Resep Formula:</label>
                  <input
                    type="text"
                    value={form.recipe_name}
                    onChange={(e) => setForm({ ...form, recipe_name: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Nama Customer:</label>
                  <input
                    type="text"
                    value={form.customer}
                    onChange={(e) => setForm({ ...form, customer: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Artikel Kain:</label>
                  <input
                    type="text"
                    value={form.article}
                    onChange={(e) => setForm({ ...form, article: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Kode Warna:</label>
                  <input
                    type="text"
                    value={form.color_code}
                    onChange={(e) => setForm({ ...form, color_code: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded font-mono outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Nama Warna:</label>
                  <input
                    type="text"
                    value={form.color_name}
                    onChange={(e) => setForm({ ...form, color_name: e.target.value })}
                    className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-[#24303f] p-3 rounded border border-gray-700">
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Berat Kain (kg):</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.fabric_weight_kg}
                    onChange={(e) => setForm({ ...form, fabric_weight_kg: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-[#1c2434] border border-gray-700 text-white px-3 py-2 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Liquor Ratio (1:x):</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form.liquor_ratio}
                    onChange={(e) => setForm({ ...form, liquor_ratio: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-[#1c2434] border border-gray-700 text-white px-3 py-2 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 font-medium mb-1">Total Air Dihitung (L):</label>
                  <input
                    type="text"
                    disabled
                    value={`${(form.fabric_weight_kg * form.liquor_ratio).toFixed(1)} Liter`}
                    className="w-full bg-[#1c2434] border border-gray-700 text-emerald-400 font-bold px-3 py-2 rounded font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-700">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="bg-gray-700 text-white px-4 py-2 rounded"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="bg-primary hover:bg-opacity-90 text-white font-semibold px-5 py-2 rounded flex items-center gap-1.5"
                >
                  <Plus className="h-4 w-4" />
                  Simpan Batch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: TRANSFER MESIN (DlgMachineBatchTransfer) */}
      {transferModalOpen && transferBatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-700 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Cpu className="h-5 w-5 text-amber-400" />
                Pindah Alokasi Mesin (Batch Transfer)
              </h3>
              <button onClick={() => setTransferModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-gray-300">
                Pindahkan batch <span className="font-bold text-white">{transferBatch.batch_no}</span> (Ref: {transferBatch.reference_no}) dari mesin <span className="text-rose-400 font-bold">{transferBatch.machine_no}</span> ke mesin tujuan:
              </p>

              <div>
                <label className="block text-gray-300 font-medium mb-1">Mesin Tujuan Baru:</label>
                <select
                  value={targetMachine}
                  onChange={(e) => setTargetMachine(e.target.value)}
                  className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded font-mono outline-none"
                >
                  {MACHINE_OPTIONS.filter(m => m !== 'SEMUA' && m !== transferBatch.machine_no).map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-700">
                <button
                  type="button"
                  onClick={() => setTransferModalOpen(false)}
                  className="bg-gray-700 text-white px-3 py-1.5 rounded"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleExecuteTransfer}
                  className="bg-amber-600 hover:bg-amber-500 text-white font-semibold px-4 py-1.5 rounded"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-gray-700 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Send className="h-5 w-5 text-emerald-400" />
                Kirim Batch ke Kontroler FTP (SETEX 797CE / 777)
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
                        setDispatchModel('797');
                      }
                    }}
                    placeholder="192.168.1.95"
                    className="w-full bg-[#1c2434] border border-gray-600 text-emerald-400 font-mono font-bold rounded px-2.5 py-1.5 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 block mt-1">Default 797CE: 192.168.1.95</span>
                </div>

                <div>
                  <label className="block text-gray-300 font-medium mb-1">Tipe Kontroler / Folder:</label>
                  <select
                    value={dispatchModel}
                    onChange={(e) => setDispatchModel(e.target.value)}
                    className="w-full bg-[#1c2434] border border-gray-600 text-amber-300 font-bold rounded px-2.5 py-1.5 outline-none"
                  >
                    <option value="797">SETEX 797CE (/Flashdisk/SC797CE/BATCH)</option>
                    <option value="777">SETEX 777 (/Storage/sc777ce/BATCH)</option>
                  </select>
                  <span className="text-[10px] text-gray-400 block mt-1">Auto-fallback aktif jika folder belum ada</span>
                </div>
              </div>

              <div className="text-[11px] text-gray-400 bg-black/20 p-2.5 rounded border border-gray-800 space-y-1">
                <span className="font-bold text-gray-300">File biner yang langsung diunggah:</span>
                <ul className="list-disc list-inside text-slate-300">
                  <li><code className="text-emerald-400">BATCHREF.REF</code> (762-byte Secom binary structure)</li>
                  <li><code className="text-emerald-400">M_{String(batchToDispatch.program_no || 1).padStart(4, '0')}.PRG</code> (Biner program eksekusi mikro)</li>
                </ul>
                <div className="text-gray-400 pt-1 border-t border-gray-800">
                  Path remote: <strong className="text-amber-300 font-mono">{dispatchModel === '797' ? '/Flashdisk/SC797CE/BATCH' : '/Storage/sc777ce/BATCH'}</strong>
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

export default BatchListView;
