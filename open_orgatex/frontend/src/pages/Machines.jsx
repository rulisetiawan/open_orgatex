import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Server,
  Plus,
  Search,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Database,
  Activity,
  LineChart,
  Radar,
  Sliders,
  Network,
  Settings,
  FlaskConical,
  Check,
  ExternalLink,
  Edit,
  ShieldCheck,
  Flame
} from 'lucide-react';

const API_BASE = '/api';

const Machines = () => {
  const navigate = useNavigate();
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(false);

  // Modals
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [snifferModalOpen, setSnifferModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('general'); // 'general', 'address', 'recipe', 'tanks', 'automation'

  // Scanner state
  const [scanning, setScanning] = useState(false);
  const [scanStartIp, setScanStartIp] = useState('172.16.110.101');
  const [scanEndIp, setScanEndIp] = useState('172.16.110.110');
  const [detectedControllers, setDetectedControllers] = useState([]);

  // Diagnostics test state
  const [testingMachine, setTestingMachine] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [fetchingConfig, setFetchingConfig] = useState(null);

  // Form State (Matches OrgaTEX UCMachineEdit & MachineContainer)
  const defaultForm = {
    machine_no: '',
    internal_no: '',
    display_name: '',
    group_name: 'Dyeing Section A',
    controller_type: 'SECOM 777 (Windows CE)',
    kind_of_machine: 'High Temp Jet Dyeing',
    ip_address: '172.16.110.101',
    tcp_port: 50100,
    ftp_port: 21,
    share_folder_path: '/Network/F/OT/',
    capacity_kg: 350.0,
    default_liquor_ratio: 8.0,
    tanks_count: 2,
    batch_weight_calc: 'Digital Scale / Timbangan',
    liquor_amount_calc: 'Liquor Ratio x Batch Weight',
    auto_download: true,
    manual_batch_start: false,
    allow_proc_pic_edit: true,
    polling_interval_sec: 5,
    is_active: true,
    auto_fetch_config: true,
  };

  const [form, setForm] = useState(defaultForm);
  const [isEditing, setIsEditing] = useState(false);

  const fetchMachines = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/machines/`);
      if (res.ok) {
        const data = await res.json();
        setMachines(data);
      }
    } catch (err) {
      console.error('Gagal mengambil daftar mesin:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMachines();
  }, []);

  // Run Sniffer
  const handleStartScan = async () => {
    setScanning(true);
    setDetectedControllers([]);
    try {
      const res = await fetch(`${API_BASE}/machines/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_ip: scanStartIp,
          end_ip: scanEndIp,
          timeout_sec: 1.0,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setDetectedControllers(data.controllers || []);
      }
    } catch (err) {
      alert(`Gagal memindai jaringan: ${err.message}`);
    } finally {
      setScanning(false);
    }
  };

  // Import detected controller from sniffer
  const handleImportController = (ctrl) => {
    const is797 = ctrl.ip_address === '192.168.1.95' || ctrl.machine_no === 'DA01' || (ctrl.controller_type && ctrl.controller_type.includes('797'));
    setForm({
      ...defaultForm,
      machine_no: ctrl.machine_no,
      display_name: ctrl.display_name,
      ip_address: ctrl.ip_address,
      controller_type: is797 ? 'SETEX 797CE (Windows CE)' : ctrl.controller_type,
      kind_of_machine: ctrl.kind_of_machine,
      ftp_port: 21,
      share_folder_path: is797 ? '/Flashdisk/SC797CE' : '/Network/F/OT/',
    });
    setSnifferModalOpen(false);
    setIsEditing(false);
    setActiveTab('general');
    setEditModalOpen(true);
  };

  // Open Edit Modal for existing machine
  const handleOpenEdit = (m) => {
    const is797 = m.ip_address === '192.168.1.95' || m.machine_no === 'DA01' || m.machine_no === 'M_95' || (m.controller_type && m.controller_type.includes('797'));
    setForm({
      machine_no: m.machine_no,
      internal_no: m.internal_no || '',
      display_name: m.display_name || m.machine_no,
      group_name: m.group_name || (is797 ? 'Dyeing Sample / DA' : 'Dyeing Section A'),
      controller_type: is797 ? 'SETEX 797CE (Windows CE)' : (m.controller_type || 'SECOM 777 (Windows CE)'),
      kind_of_machine: m.kind_of_machine || 'High Temp Jet Dyeing',
      ip_address: m.ip_address,
      tcp_port: m.tcp_port || 50100,
      ftp_port: m.ftp_port || 21,
      share_folder_path: is797 ? '/Flashdisk/SC797CE' : (m.share_folder_path || '/Network/F/OT/'),
      capacity_kg: m.capacity_kg || 350.0,
      default_liquor_ratio: m.default_liquor_ratio || 8.0,
      tanks_count: m.tanks_count || 2,
      batch_weight_calc: m.batch_weight_calc || 'Digital Scale / Timbangan',
      liquor_amount_calc: m.liquor_amount_calc || 'Liquor Ratio x Batch Weight',
      auto_download: m.auto_download !== undefined ? m.auto_download : true,
      manual_batch_start: m.manual_batch_start !== undefined ? m.manual_batch_start : false,
      allow_proc_pic_edit: m.allow_proc_pic_edit !== undefined ? m.allow_proc_pic_edit : true,
      polling_interval_sec: m.polling_interval_sec || 5,
      is_active: m.is_active !== undefined ? m.is_active : true,
    });
    setIsEditing(true);
    setActiveTab('general');
    setEditModalOpen(true);
  };

  // Test Connection
  const handleTestConnection = async (m) => {
    setTestingMachine(m.machine_no);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/machines/${m.machine_no}/test`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setTestResult(data);
        fetchMachines();
      }
    } catch (err) {
      alert(`Gagal koneksi ke server: ${err.message}`);
    } finally {
      setTestingMachine(null);
    }
  };

  // Fetch HMI config via FTP
  const handleFetchConfig = async (machineNo) => {
    setFetchingConfig(machineNo);
    try {
      const res = await fetch(`${API_BASE}/machines/${machineNo}/fetch-config`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        const fileNames = data.downloaded && data.downloaded.length > 0
          ? data.downloaded.map(d => `• ${d.filename} (${(d.size_bytes / 1024).toFixed(1)} KB)`).join('\n')
          : 'File .CNF';
        alert(`[SUKSES] ${data.message}\n\nFile tersimpan & disinkronkan ke workspace:\n${fileNames}`);
        fetchMachines();
      } else {
        alert(`[PERINGATAN] ${data.message || 'Gagal mengunduh file config dari HMI via FTP.'}\nStatus: ${data.status}`);
      }
    } catch (err) {
      alert(`Gagal koneksi ke kontroler: ${err.message}`);
    } finally {
      setFetchingConfig(null);
    }
  };

  // Save Machine to PostgreSQL
  const handleSubmitMachine = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/machines/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.config_fetch && data.config_fetch.success) {
          const files = data.config_fetch.downloaded.map(d => d.filename).join(', ');
          alert(`[SUKSES] ${data.message}\nFile HMI berhasil diunduh: ${files}`);
        } else if (data.config_fetch && !data.config_fetch.success) {
          alert(`[INFORMASI] ${data.message}`);
        }
        setEditModalOpen(false);
        setForm(defaultForm);
        fetchMachines();
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Gagal menyimpan konfigurasi mesin'}`);
      }
    } catch (err) {
      alert(`Koneksi error: ${err.message}`);
    }
  };

  // Delete Machine
  const handleDeleteMachine = async (machineNo) => {
    if (!window.confirm(`Hapus konfigurasi mesin ${machineNo} dari database?`)) return;
    try {
      const res = await fetch(`${API_BASE}/machines/${machineNo}`, { method: 'DELETE' });
      if (res.ok) {
        fetchMachines();
      }
    } catch (err) {
      alert(`Gagal menghapus mesin: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* HEADER & TOOLBAR */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-black dark:text-white">
            Konfigurasi Mesin
          </h2>
        </div>

        {/* ACTIONS */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => {
              setSnifferModalOpen(true);
              setDetectedControllers([]);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-meta-5 hover:bg-meta-5/90 rounded shadow-xs transition-colors cursor-pointer"
          >
            <Radar className="h-4 w-4" />
            Pindai Jaringan
          </button>

          <button
            onClick={() => {
              setForm(defaultForm);
              setIsEditing(false);
              setActiveTab('general');
              setEditModalOpen(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-primary hover:bg-primary/90 rounded shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            Tambah Mesin
          </button>

          <button
            onClick={fetchMachines}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-xs cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* TEST DIAGNOSTIC RESULT POPUP */}
      {testResult && (
        <div className="rounded border border-primary/30 bg-blue-50/50 dark:bg-meta-4/20 p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-primary flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-success" />
              Hasil Uji Diagnostik Mesin: {testResult.machine_no} ({testResult.ip_address})
            </span>
            <button onClick={() => setTestResult(null)} className="text-xs text-gray-400 hover:text-black">Tutup</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="bg-white dark:bg-boxdark p-2 rounded border border-stroke dark:border-strokedark">
              <span className="text-gray-400 block text-[10px]">ICMP Ping:</span>
              <span className={`font-bold ${testResult.ping ? 'text-success' : 'text-danger'}`}>
                {testResult.ping ? '● TERHUBUNG' : '○ GAGAL'}
              </span>
            </div>
            <div className="bg-white dark:bg-boxdark p-2 rounded border border-stroke dark:border-strokedark">
              <span className="text-gray-400 block text-[10px]">Port FTP (21):</span>
              <span className={`font-bold ${testResult.ftp_port_21 ? 'text-success' : 'text-danger'}`}>
                {testResult.ftp_port_21 ? '● TERBUKA & AKTIF' : '○ TUTUP'}
              </span>
            </div>
            <div className="bg-white dark:bg-boxdark p-2 rounded border border-stroke dark:border-strokedark">
              <span className="text-gray-400 block text-[10px]">STATUS.ACT Storage:</span>
              <span className={`font-bold ${testResult.status_act_detected ? 'text-success' : 'text-warning'}`}>
                {testResult.status_act_detected ? '● TERDETEKSI (LIVE)' : '○ BELUM DIBACA'}
              </span>
            </div>
            <div className="bg-white dark:bg-boxdark p-2 rounded border border-stroke dark:border-strokedark">
              <span className="text-gray-400 block text-[10px]">Status Keseluruhan:</span>
              <span className="font-bold text-success">
                {testResult.overall_status}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* MACHINE TILES LIST (UCMachineList) */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {machines.map((m) => {
          const isOnline = m.status === 'ONLINE' || m.status === 'RUNNING';
          return (
            <div
              key={m.machine_no}
              className="rounded-lg border border-stroke bg-white dark:border-strokedark dark:bg-boxdark shadow-sm hover:shadow-md transition-shadow overflow-hidden"
            >
              <div className="flex items-center justify-between p-4 border-b border-stroke dark:border-strokedark">
                <div className="flex items-center gap-2.5">
                  <div className={`w-3 h-3 rounded-full ${isOnline ? 'bg-success animate-pulse' : 'bg-gray-400'}`} />
                  <div>
                    <h3 className="font-extrabold text-base text-black dark:text-white">
                      Mesin {m.machine_no}
                    </h3>
                    <span className="text-[11px] text-gray-500">{m.display_name}</span>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${m.status === 'RUNNING'
                  ? 'bg-meta-3 text-white'
                  : isOnline
                    ? 'bg-success/10 text-success'
                    : 'bg-gray-100 text-gray-500 dark:bg-meta-4'
                  }`}>
                  {m.status}
                </span>
              </div>

              <div className="p-4 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">IP Kontroler HMI:</span>
                  <span className="font-mono font-bold text-primary">{m.ip_address}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Grup Mesin:</span>
                  <span className="font-medium text-black dark:text-white">{m.group_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tipe Kontroler:</span>
                  <span className="font-medium text-black dark:text-white">{m.controller_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Kapasitas / Liquor Ratio:</span>
                  <span className="font-medium text-black dark:text-white">{m.capacity_kg} kg | 1:{m.default_liquor_ratio}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Folder Data:</span>
                  <span className="font-mono text-gray-600 dark:text-gray-400 truncate max-w-[160px]">{m.share_folder_path}</span>
                </div>

                <div className="flex justify-between items-center py-1.5 px-2 bg-gray-50 dark:bg-meta-4/20 rounded border border-stroke/50 dark:border-strokedark/50">
                  <span className="text-gray-500 text-[11px]">Konfigurasi HMI:</span>
                  {m.has_custom_hmi_config ? (
                    <span className="text-success font-bold flex items-center gap-1 text-[11px]">
                      <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                      HMI Ready (Asli)
                    </span>
                  ) : (
                    <span className="text-amber-500 font-bold flex items-center gap-1 text-[11px]">
                      <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
                      Baseline Standar
                    </span>
                  )}
                </div>

                {/* ACTION BUTTONS */}
                <div className="pt-3 border-t border-stroke dark:border-strokedark flex items-center justify-between gap-1.5">
                  <button
                    onClick={() => handleFetchConfig(m.machine_no)}
                    disabled={fetchingConfig === m.machine_no}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2 bg-emerald-50 dark:bg-emerald-950/30 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded font-bold text-[11px] transition-colors"
                    title="Tarik File Config (.CNF) dari HMI Kontroler via FTP"
                  >
                    <RefreshCw className={`h-3 w-3 ${fetchingConfig === m.machine_no ? 'animate-spin' : ''}`} />
                    {fetchingConfig === m.machine_no ? 'Mengunduh...' : 'Tarik Config'}
                  </button>

                  <button
                    onClick={() => handleTestConnection(m)}
                    disabled={testingMachine === m.machine_no}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2 bg-gray-100 dark:bg-meta-4 hover:bg-gray-200 text-black dark:text-white rounded font-medium text-[11px]"
                  >
                    <Network className="h-3 w-3 text-primary" />
                    {testingMachine === m.machine_no ? 'Menguji...' : 'Uji Koneksi'}
                  </button>

                  <button
                    onClick={() => navigate(`/process-analyser?machine=${m.machine_no}`)}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2 bg-primary/10 hover:bg-primary/20 text-primary rounded font-bold text-[11px]"
                  >
                    <LineChart className="h-3 w-3" />
                    Grafik
                  </button>

                  <button
                    onClick={() => handleOpenEdit(m)}
                    className="p-1.5 text-gray-500 hover:text-primary rounded hover:bg-gray-100 dark:hover:bg-meta-4"
                    title="Edit Konfigurasi"
                  >
                    <Edit className="h-4 w-4" />
                  </button>

                  <button
                    onClick={() => handleDeleteMachine(m.machine_no)}
                    className="p-1.5 text-gray-500 hover:text-danger rounded hover:bg-gray-100 dark:hover:bg-meta-4"
                    title="Hapus Mesin"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* MODAL 1: ORGATEX SECOM CE SNIFFER (DlgAddOnlineMachine) */}
      {snifferModalOpen && (
        <div className="fixed inset-0 z-99999 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-3xl rounded-lg bg-white dark:bg-boxdark p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <div className="flex items-center gap-2">
                <Radar className="h-5 w-5 text-meta-5" />
                <h3 className="text-base font-bold text-black dark:text-white">
                  Pindai Mesin Online
                </h3>
              </div>
              <button
                onClick={() => setSnifferModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-gray-500">
              Pindai subnet jaringan pabrik secara otomatis untuk mendeteksi kontroler SETEX Secom 777 yang sedang menyala dan online.
            </p>

            {/* SCANNER RANGE INPUT */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 bg-gray-50 dark:bg-meta-4/20 rounded border border-stroke dark:border-strokedark">
              <div>
                <label className="text-[10px] font-bold text-gray-500 uppercase block mb-1">Mulai IP Range:</label>
                <input
                  type="text"
                  value={scanStartIp}
                  onChange={(e) => setScanStartIp(e.target.value)}
                  className="w-full text-xs font-mono font-bold p-2 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-gray-500 uppercase block mb-1">Sampai IP Range:</label>
                <input
                  type="text"
                  value={scanEndIp}
                  onChange={(e) => setScanEndIp(e.target.value)}
                  className="w-full text-xs font-mono font-bold p-2 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleStartScan}
                  disabled={scanning}
                  className="w-full flex items-center justify-center gap-2 py-2 text-xs font-bold text-white bg-meta-5 hover:bg-meta-5/90 rounded shadow-sm"
                >
                  <Search className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
                  {scanning ? 'Memindai Jaringan...' : 'Mulai Pindai Subnet'}
                </button>
              </div>
            </div>

            {/* DETECTED CONTROLLERS TABLE */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-black dark:text-white">
                Kontroler SETEX Terdeteksi ({detectedControllers.length} Unit Ditemukan)
              </h4>
              <div className="max-h-60 overflow-y-auto border border-stroke dark:border-strokedark rounded">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300">
                    <tr>
                      <th className="py-2 px-3">Nomor Mesin</th>
                      <th className="py-2 px-3">Alamat IP</th>
                      <th className="py-2 px-3">Tipe Kontroler</th>
                      <th className="py-2 px-3">Program Aktif</th>
                      <th className="py-2 px-3">Port FTP 21</th>
                      <th className="py-2 px-3 text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stroke dark:divide-strokedark">
                    {detectedControllers.length > 0 ? (
                      detectedControllers.map((ctrl) => (
                        <tr key={ctrl.ip_address} className="hover:bg-gray-50 dark:hover:bg-meta-4/20">
                          <td className="py-2.5 px-3 font-bold font-mono text-black dark:text-white">
                            {ctrl.machine_no}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-primary">
                            {ctrl.ip_address}
                          </td>
                          <td className="py-2.5 px-3">{ctrl.controller_type}</td>
                          <td className="py-2.5 px-3 font-semibold text-meta-3">{ctrl.program_code}</td>
                          <td className="py-2.5 px-3">
                            <span className="text-[10px] font-bold text-success bg-success/10 px-1.5 py-0.5 rounded">
                              ONLINE
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => handleImportController(ctrl)}
                              className="px-2.5 py-1 text-[11px] font-bold text-white bg-primary hover:bg-primary/90 rounded shadow-sm"
                            >
                              + Daftarkan Mesin
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="6" className="py-6 text-center text-gray-400">
                          {scanning ? 'Sedang memindai alamat IP pada jaringan...' : 'Klik "Mulai Pindai Subnet" untuk mendeteksi kontroler di jaringan.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-stroke dark:border-strokedark">
              <button
                onClick={() => setSnifferModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-meta-4 rounded"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: ORGATEX MACHINE CONFIGURATION FORM (DlgAddMachine / UCMachineEdit) */}
      {editModalOpen && (
        <div className="fixed inset-0 z-99999 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-4xl rounded-lg bg-white dark:bg-boxdark p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            {/* MODAL HEADER */}
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5 text-primary" />
                <h3 className="text-base font-bold text-black dark:text-white">
                  {isEditing ? `Edit Konfigurasi Mesin ${form.machine_no}` : 'Tambah Konfigurasi Mesin Baru'}
                </h3>
              </div>
              <button
                onClick={() => setEditModalOpen(false)}
                className="text-gray-400 hover:text-black dark:hover:text-white font-bold"
              >
                ✕
              </button>
            </div>

            {/* TAB PANELS (ORGATEX tgPanels PARITY) */}
            <div className="flex border-b border-stroke dark:border-strokedark space-x-1">
              <button
                type="button"
                onClick={() => setActiveTab('general')}
                className={`py-2 px-4 text-xs font-bold border-b-2 transition-colors ${activeTab === 'general'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
              >
                1. Data Umum (General)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('address')}
                className={`py-2 px-4 text-xs font-bold border-b-2 transition-colors ${activeTab === 'address'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
              >
                2. Jaringan & Komunikasi (Address)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('recipe')}
                className={`py-2 px-4 text-xs font-bold border-b-2 transition-colors ${activeTab === 'recipe'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
              >
                3. Resep & Kalkulasi (Recipe)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('tanks')}
                className={`py-2 px-4 text-xs font-bold border-b-2 transition-colors ${activeTab === 'tanks'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
              >
                4. Tangki & Dosing (Tanks)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('automation')}
                className={`py-2 px-4 text-xs font-bold border-b-2 transition-colors ${activeTab === 'automation'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
              >
                5. Otomasi & Fitur
              </button>
            </div>

            <form onSubmit={handleSubmitMachine} className="space-y-4">
              {/* TAB 1: DATA UMUM (lpGeneralData) */}
              {activeTab === 'general' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Nomor Mesin (ID Unik Controller):
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Contoh: 1A, A001, B002"
                      value={form.machine_no}
                      onChange={(e) => setForm({ ...form, machine_no: e.target.value.toUpperCase() })}
                      className="w-full text-xs font-mono font-bold p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                    <span className="text-[10px] text-gray-400">Harus sesuai dengan nama folder di /OT/MACHINES/ atau ID SETEX.</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Nama Tampilan Mesin (Display Name):
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Contoh: Thies Eco-Soft 1A"
                      value={form.display_name}
                      onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                      className="w-full text-xs p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Grup Mesin (Machine Group):
                    </label>
                    <select
                      value={form.group_name}
                      onChange={(e) => setForm({ ...form, group_name: e.target.value })}
                      className="w-full text-xs p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    >
                      <option value="Dyeing Section A">Dyeing Section A (Jet Dyeing)</option>
                      <option value="Dyeing Section B">Dyeing Section B (Soft Flow)</option>
                      <option value="Dyeing Section C">Dyeing Section C (Jigger)</option>
                      <option value="Sampling Lab">Sampling Lab</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Jenis Kontroler SETEX:
                    </label>
                    <select
                      value={form.controller_type}
                      onChange={(e) => {
                        const val = e.target.value;
                        const is797 = val.includes('797');
                        setForm({
                          ...form,
                          controller_type: val,
                          share_folder_path: is797 ? '/Flashdisk/SC797CE' : (form.share_folder_path === '/Flashdisk/SC797CE' ? '/Storage/SC777CE' : form.share_folder_path)
                        });
                      }}
                      className="w-full text-xs font-semibold p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    >
                      <option value="SETEX 797CE (Windows CE)">SETEX 797CE (Windows CE) - /Flashdisk/SC797CE</option>
                      <option value="SECOM 777 (Windows CE)">SECOM 777 (Windows CE) - /Storage/SC777CE</option>
                      <option value="Novatech Digital">Novatech Digital</option>
                      <option value="SECOM 737">SECOM 737</option>
                      <option value="SECOM 505">SECOM 505</option>
                      <option value="SECOM 838">SECOM 838</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Jenis Mesin (Kind of Machine):
                    </label>
                    <select
                      value={form.kind_of_machine}
                      onChange={(e) => setForm({ ...form, kind_of_machine: e.target.value })}
                      className="w-full text-xs p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    >
                      <option value="High Temp Jet Dyeing">High Temp Jet Dyeing (HT Bejana)</option>
                      <option value="Atmospheric Overflow">Atmospheric Overflow</option>
                      <option value="Jigger Dyeing">Jigger Dyeing</option>
                      <option value="Yarn Package">Yarn Package / Cones</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Nomor Internal PLC (Stasiun Arcnet / Ethernet):
                    </label>
                    <input
                      type="text"
                      placeholder="Contoh: 1, 2, 10"
                      value={form.internal_no}
                      onChange={(e) => setForm({ ...form, internal_no: e.target.value })}
                      className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                  </div>
                </div>
              )}

              {/* TAB 2: ALAMAT & JARINGAN (lpAddress) */}
              {activeTab === 'address' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs font-bold text-black dark:text-white block mb-1">
                        Alamat IP Kontroler (HMI):
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="Contoh: 172.16.110.101"
                        value={form.ip_address}
                        onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
                        className="w-full text-xs font-mono font-bold p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-primary outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-xs font-bold text-black dark:text-white block mb-1">
                        Port Komunikasi SETEX:
                      </label>
                      <input
                        type="number"
                        value={form.tcp_port}
                        onChange={(e) => setForm({ ...form, tcp_port: parseInt(e.target.value) })}
                        className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                      />
                      <span className="text-[10px] text-gray-400">Default: 50100 atau 50000.</span>
                    </div>

                    <div>
                      <label className="text-xs font-bold text-black dark:text-white block mb-1">
                        Port FTP (File Storage):
                      </label>
                      <input
                        type="number"
                        value={form.ftp_port}
                        onChange={(e) => setForm({ ...form, ftp_port: parseInt(e.target.value) })}
                        className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                      />
                      <span className="text-[10px] text-gray-400">Default Port FTP: 21.</span>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Jalur Folder Sharing (Read-Only Source):
                    </label>
                    <input
                      type="text"
                      value={form.share_folder_path}
                      onChange={(e) => setForm({ ...form, share_folder_path: e.target.value })}
                      className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                    <span className="text-[10px] text-gray-400">Contoh: /Network/F/OT/ atau /Storage/sc777ce/STATUS/</span>
                  </div>
                </div>
              )}

              {/* TAB 3: RESEP & KALKULASI (lpRecipe) */}
              {activeTab === 'recipe' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Kapasitas Nominal Mesin (kg):
                    </label>
                    <input
                      type="number"
                      step="1"
                      value={form.capacity_kg}
                      onChange={(e) => setForm({ ...form, capacity_kg: parseFloat(e.target.value) })}
                      className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Rasio Larutan Standar (Liquor Ratio 1:X):
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={form.default_liquor_ratio}
                      onChange={(e) => setForm({ ...form, default_liquor_ratio: parseFloat(e.target.value) })}
                      className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Metode Penentuan Bobot Kain:
                    </label>
                    <select
                      value={form.batch_weight_calc}
                      onChange={(e) => setForm({ ...form, batch_weight_calc: e.target.value })}
                      className="w-full text-xs p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    >
                      <option value="Digital Scale / Timbangan">Digital Scale / Timbangan Otomatis</option>
                      <option value="Manual Input Operator">Input Manual Operator HMI</option>
                      <option value="Production Order Weight">Berdasarkan Order Produksi / Lot</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Metode Kalkulasi Volume Air:
                    </label>
                    <select
                      value={form.liquor_amount_calc}
                      onChange={(e) => setForm({ ...form, liquor_amount_calc: e.target.value })}
                      className="w-full text-xs p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    >
                      <option value="Liquor Ratio x Batch Weight">Liquor Ratio x Berat Kain (Liter)</option>
                      <option value="Fixed Volume">Volume Tetap (Fixed Volume)</option>
                    </select>
                  </div>
                </div>
              )}

              {/* TAB 4: TANGKI & DOSING (lpTanks) */}
              {activeTab === 'tanks' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-black dark:text-white block mb-1">
                      Jumlah Tangki Obat Bantu / Dosing (Tanks):
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="6"
                      value={form.tanks_count}
                      onChange={(e) => setForm({ ...form, tanks_count: parseInt(e.target.value) })}
                      className="w-full text-xs font-mono p-2.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white outline-none"
                    />
                    <span className="text-[10px] text-gray-400">Biasanya 2 tangki (Tangki 1 & Tangki 2).</span>
                  </div>
                </div>
              )}

              {/* TAB 5: OTOMASI (lpCommunication) */}
              {activeTab === 'automation' && (
                <div className="space-y-3 p-4 bg-gray-50 dark:bg-meta-4/20 rounded border border-stroke dark:border-strokedark">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="auto_download"
                      checked={form.auto_download}
                      onChange={(e) => setForm({ ...form, auto_download: e.target.checked })}
                      className="h-4 w-4 rounded text-primary focus:ring-primary"
                    />
                    <label htmlFor="auto_download" className="text-xs font-semibold text-black dark:text-white">
                      Auto Download Program Celup (Otomatis dispatch ke antrean mesin saat batch rilis)
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="manual_batch_start"
                      checked={form.manual_batch_start}
                      onChange={(e) => setForm({ ...form, manual_batch_start: e.target.checked })}
                      className="h-4 w-4 rounded text-primary focus:ring-primary"
                    />
                    <label htmlFor="manual_batch_start" className="text-xs font-semibold text-black dark:text-white">
                      Manual Batch Start (Operator harus menekan tombol start fisik di kontroler)
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="allow_proc_pic_edit"
                      checked={form.allow_proc_pic_edit}
                      onChange={(e) => setForm({ ...form, allow_proc_pic_edit: e.target.checked })}
                      className="h-4 w-4 rounded text-primary focus:ring-primary"
                    />
                    <label htmlFor="allow_proc_pic_edit" className="text-xs font-semibold text-black dark:text-white">
                      Izinkan Intervensi Operator dari Process Picture (Online Status OLN420)
                    </label>
                  </div>
                </div>
              )}

              {/* AUTO-FETCH CONFIG HMI OPTION BANNER */}
              <div className="p-3 bg-blue-50/70 dark:bg-meta-4/30 border border-primary/30 rounded-lg flex items-center justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <input
                    type="checkbox"
                    id="auto_fetch_config"
                    checked={form.auto_fetch_config}
                    onChange={(e) => setForm({ ...form, auto_fetch_config: e.target.checked })}
                    className="mt-0.5 h-4 w-4 rounded text-primary focus:ring-primary cursor-pointer"
                  />
                  <div>
                    <label htmlFor="auto_fetch_config" className="text-xs font-bold text-black dark:text-white cursor-pointer flex items-center gap-1.5">
                      <RefreshCw className="h-3.5 w-3.5 text-primary" />
                      Otomatis Unduh & Sinkronisasi File Config (.CNF) dari HMI via FTP
                    </label>
                    <span className="text-[11px] text-gray-500 dark:text-gray-400 block mt-0.5">
                      Sistem akan langsung menghubungi IP kontroler ({form.ip_address || '...'}) di port 21 untuk mengunduh
                      <span className="font-mono text-primary font-bold"> TYPECONF.CNF</span>,
                      <span className="font-mono text-primary font-bold"> CONFTEXT.CNF</span>, dan
                      <span className="font-mono text-primary font-bold"> MACHCONF.CNF</span> ke folder workspace mesin.
                    </span>
                  </div>
                </div>
                <span className="shrink-0 text-[10px] font-extrabold bg-success/15 text-success border border-success/30 px-2 py-0.5 rounded">
                  DIREKOMENDASIKAN
                </span>
              </div>

              {/* FOOTER BUTTONS */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-stroke dark:border-strokedark">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-meta-4 rounded"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-1.5 px-5 py-2 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded shadow-md transition-colors"
                >
                  <Database className="h-4 w-4" />
                  Simpan ke PostgreSQL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Machines;
