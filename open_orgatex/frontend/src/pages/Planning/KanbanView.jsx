import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { 
  Plus, 
  Download, 
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
  Sparkles 
} from 'lucide-react';
import axios from 'axios';

const API_BASE = '/api/planning';

const COLUMN_DEFS = {
  QUEUED: { name: 'Antrean Produksi (Queued)', color: 'border-amber-500/50 bg-amber-50/10 dark:bg-amber-950/20 text-amber-500' },
  WAITING_LA: { name: 'Menunggu Dosing LA', color: 'border-blue-500/50 bg-blue-50/10 dark:bg-blue-950/20 text-blue-500' },
  RUNNING: { name: 'Sedang Proses Celup (Running)', color: 'border-emerald-500/50 bg-emerald-50/10 dark:bg-emerald-950/20 text-emerald-500' },
  COMPLETED: { name: 'Selesai (Completed)', color: 'border-slate-500/50 bg-slate-50/10 dark:bg-slate-900/30 text-slate-400' },
};

const MACHINE_OPTIONS = ['SEMUA', 'TD12', 'TD13', 'B012', 'E013', 'M01'];

const KanbanView = () => {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedMachine, setSelectedMachine] = useState('SEMUA');
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
    machine_no: 'TD12',
    program_no: 401,
    recipe_name: 'Reactive Blue Standard Formula',
    customer: 'PT. ARTA PERMAI',
    article: 'CM 30S RIB 100% Cotton',
    color_code: '1650159',
    color_name: 'UNGU TUA',
    fabric_weight_kg: 325.85,
    liquor_ratio: 8.0,
  });

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get(API_BASE);
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
        setAvailablePrograms(res.data.map(p => ({
          no: p.program_no,
          name: `M_${String(p.program_no).padStart(4, '0')}.PRG - ${p.name || 'Program'}`
        })));
      }
    } catch (err) {
      // Keep defaults
    }
  };

  useEffect(() => {
    fetchBatches();
    fetchPrograms();
  }, []);

  // Filter batches by machine
  const filteredBatches = selectedMachine === 'SEMUA' 
    ? batches 
    : batches.filter(b => b.machine_no === selectedMachine);

  // Group by Column Status
  const columnsData = {
    QUEUED: filteredBatches.filter(b => b.status === 'QUEUED').sort((a,b) => (a.position || 0) - (b.position || 0)),
    WAITING_LA: filteredBatches.filter(b => b.status === 'WAITING_LA').sort((a,b) => (a.position || 0) - (b.position || 0)),
    RUNNING: filteredBatches.filter(b => b.status === 'RUNNING').sort((a,b) => (a.position || 0) - (b.position || 0)),
    COMPLETED: filteredBatches.filter(b => b.status === 'COMPLETED').sort((a,b) => (a.position || 0) - (b.position || 0)),
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
      await axios.post(API_BASE, form);
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
          {MACHINE_OPTIONS.map(m => (
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(COLUMN_DEFS).map(([colKey, colMeta]) => {
            const items = columnsData[colKey] || [];
            return (
              <div 
                key={colKey}
                className="flex flex-col rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-[#182234] p-3 min-h-[500px]"
              >
                {/* Column Header */}
                <div className={`flex items-center justify-between pb-2.5 mb-3 border-b border-stroke dark:border-strokedark`}>
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
                              <div className="flex items-center justify-between gap-2 pt-1">
                                <button
                                  type="button"
                                  onClick={() => handleDownloadZip(item.id, item.reference_no, item.batch_no)}
                                  className="flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded bg-primary/10 hover:bg-primary/20 text-primary text-[10px] font-bold border border-primary/20 transition"
                                  title="Unduh Paket Biner BATCHREF.REF & M_xxxx.PRG (ZIP)"
                                >
                                  <Download className="h-3 w-3" />
                                  <span>Unduh ZIP</span>
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
                    {MACHINE_OPTIONS.filter(m => m !== 'SEMUA').map(m => (
                      <option key={m} value={m}>{m} (SECOM 777)</option>
                    ))}
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
                    onChange={(e) => setForm({ ...form, program_no: Number(e.target.value) })}
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
    </div>
  );
};

export default KanbanView;
