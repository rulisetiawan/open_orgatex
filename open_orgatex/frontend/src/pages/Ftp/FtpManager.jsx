import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Server, 
  Folder, 
  FileText, 
  FileCode, 
  Upload, 
  Download, 
  RefreshCw, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  HardDrive, 
  ArrowLeft, 
  Eye, 
  Activity, 
  Clock, 
  Cpu, 
  Send,
  CornerDownRight,
  Database,
  Copy,
  Scissors,
  ClipboardPaste,
  Trash2,
  FolderPlus,
  Edit2,
  FolderTree,
  ChevronRight,
  ChevronDown,
  Check,
  X,
  Laptop,
  ArrowRight,
  ArrowLeftRight,
  FileCheck2
} from 'lucide-react';

const FtpManager = () => {
  // Machine & Connection State
  const [machines, setMachines] = useState([]);
  const [selectedMachineIp, setSelectedMachineIp] = useState('172.16.110.101');
  const [ftpPort, setFtpPort] = useState(21);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // Status State
  const [connStatus, setConnStatus] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

  // Active Pane ('local' | 'remote')
  const [activePane, setActivePane] = useState('remote');

  // Local Host Explorer State
  const [localPath, setLocalPath] = useState('');
  const [localRoot, setLocalRoot] = useState('');
  const [localEntries, setLocalEntries] = useState([]);
  const [loadingLocal, setLoadingLocal] = useState(false);
  const [selectedLocalEntry, setSelectedLocalEntry] = useState(null);

  // Remote FTP Explorer State
  const [remotePath, setRemotePath] = useState('/storage/SC777CE');
  const [remoteEntries, setRemoteEntries] = useState([]);
  const [loadingRemote, setLoadingRemote] = useState(false);
  const [selectedRemoteEntry, setSelectedRemoteEntry] = useState(null);

  // Global Clipboard (supports cross-pane copy-paste / upload-download)
  const [clipboard, setClipboard] = useState(null); // { pane: 'local'|'remote', mode: 'copy'|'cut', entry: {...} }
  const [actionLoading, setActionLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  // Modals State
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [availableBatches, setAvailableBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const [dispatching, setDispatching] = useState(false);

  const [mkdirModalOpen, setMkdirModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [mkdirTargetPane, setMkdirTargetPane] = useState('remote');

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null); // { pane: 'local'|'remote', entry: {...} }

  // Quick Bookmarks for Local Host
  const localBookmarks = [
    { name: 'Root DA-TEX', path: '' },
    { name: 'Programs (PRG)', path: 'Programs' },
    { name: 'OrgaTex_Share', path: 'OrgaTex_Share' },
    { name: 'STATUS', path: 'STATUS' },
    { name: 'plain_export', path: 'plain_export' },
  ];

  // Quick Bookmarks for Remote SETEX Controller
  const remoteBookmarks = [
    { name: 'Root Controller', path: '/storage/SC777CE' },
    { name: 'STATUS (Live)', path: '/storage/SC777CE/STATUS' },
    { name: 'BATCH (Antrean)', path: '/storage/SC777CE/BATCH' },
    { name: 'Programs (Resep)', path: '/storage/SC777CE/Programs' },
    { name: 'ERRORLOG', path: '/storage/SC777CE/ERRORLOG' },
  ];

  // Toast Helper
  const showToast = (text, type = 'info') => {
    setToastMessage({ text, type });
    setTimeout(() => {
      setToastMessage(null);
    }, 4500);
  };

  // Initial Data Fetch
  useEffect(() => {
    fetchMachines();
    fetchBatches();
    browseLocalDirectory('');
    browseRemoteDirectory('/storage/SC777CE', '172.16.110.101');
  }, []);

  // Keyboard Shortcuts (Ctrl+C, Ctrl+X, Ctrl+V, Delete, Esc)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

      const activeEntry = activePane === 'local' ? selectedLocalEntry : selectedRemoteEntry;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
        if (activeEntry) {
          e.preventDefault();
          handleCopy(activePane, activeEntry);
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'x') {
        if (activeEntry) {
          e.preventDefault();
          handleCut(activePane, activeEntry);
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
        if (clipboard) {
          e.preventDefault();
          handlePaste(activePane);
        }
      } else if (e.key === 'Delete') {
        if (activeEntry) {
          e.preventDefault();
          setItemToDelete({ pane: activePane, entry: activeEntry });
          setDeleteModalOpen(true);
        }
      } else if (e.key === 'Escape') {
        if (clipboard) {
          setClipboard(null);
          showToast('Clipboard dibatalkan', 'info');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activePane, selectedLocalEntry, selectedRemoteEntry, clipboard, localPath, remotePath, selectedMachineIp, ftpPort]);

  const fetchMachines = async () => {
    try {
      const res = await axios.get('/api/machines/');
      if (res.data && res.data.length > 0) {
        setMachines(res.data);
        const firstWithIp = res.data.find(m => m.ip_address);
        if (firstWithIp) {
          setSelectedMachineIp(firstWithIp.ip_address);
          if (firstWithIp.ftp_port) setFtpPort(firstWithIp.ftp_port);
        }
      }
    } catch (err) {
      console.warn('Menggunakan default controller machine');
    }
  };

  const fetchBatches = async () => {
    try {
      const res = await axios.get('/api/planning/');
      setAvailableBatches(res.data || []);
      if (res.data && res.data.length > 0) {
        setSelectedBatchId(res.data[0].id);
      }
    } catch (err) {
      console.warn('Gagal memuat daftar batch untuk dispatch');
    }
  };

  const testConnection = async (ip = selectedMachineIp, port = ftpPort) => {
    setIsTesting(true);
    try {
      const res = await axios.post('/api/ftp/test', {
        ip: ip.trim(),
        port: parseInt(port, 10),
        username,
        password,
        timeout: 4.0
      });
      setConnStatus(res.data);
      showToast(res.data.message || 'Koneksi FTP berhasil!', 'success');
    } catch (err) {
      setConnStatus({
        status: 'OFFLINE',
        message: err.response?.data?.detail || err.message,
        latency_ms: 0
      });
      showToast('Koneksi FTP gagal: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setIsTesting(false);
    }
  };

  // Browse Local Host Directory
  const browseLocalDirectory = async (path = '') => {
    setLoadingLocal(true);
    setSelectedLocalEntry(null);
    try {
      const res = await axios.post('/api/ftp/local/browse', { path });
      setLocalEntries(res.data.entries || []);
      setLocalPath(res.data.current_path || path);
      if (res.data.root_path) setLocalRoot(res.data.root_path);
    } catch (err) {
      console.error('Error browse Local:', err);
      setLocalEntries([]);
      showToast('Gagal membaca folder lokal: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setLoadingLocal(false);
    }
  };

  // Browse Remote FTP Directory
  const browseRemoteDirectory = async (path, ip = selectedMachineIp) => {
    setLoadingRemote(true);
    setSelectedRemoteEntry(null);
    try {
      const res = await axios.post('/api/ftp/browse', {
        ip: ip.trim(),
        port: parseInt(ftpPort, 10),
        username,
        password,
        remote_path: path
      });
      setRemoteEntries(res.data.entries || []);
      setRemotePath(res.data.current_path || path);
    } catch (err) {
      console.error('Error browse FTP:', err);
      setRemoteEntries([]);
      showToast('Gagal membaca direktori remote: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setLoadingRemote(false);
    }
  };

  const handleNavigateUpLocal = () => {
    if (!localPath || localPath === localRoot) return;
    const parts = localPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = parts.join('/');
    browseLocalDirectory(parentPath || localRoot);
  };

  const handleNavigateUpRemote = () => {
    if (remotePath === '/' || !remotePath) return;
    const parts = remotePath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = '/' + parts.join('/');
    browseRemoteDirectory(parentPath || '/');
  };

  // Copy & Cut Handlers
  const handleCopy = (pane, entry) => {
    if (!entry) return;
    setClipboard({ pane, mode: 'copy', entry });
    showToast(`Disalin dari ${pane.toUpperCase()}: ${entry.name}`, 'info');
  };

  const handleCut = (pane, entry) => {
    if (!entry) return;
    setClipboard({ pane, mode: 'cut', entry });
    showToast(`Dipotong dari ${pane.toUpperCase()}: ${entry.name}`, 'info');
  };

  // Paste Handler (supports Cross-Pane Transfer: Local->Remote or Remote->Local)
  const handlePaste = async (targetPane = activePane) => {
    if (!clipboard) return;
    setActionLoading(true);

    try {
      // CASE 1: Cross-Pane Transfer (Local to Remote -> Upload)
      if (clipboard.pane === 'local' && targetPane === 'remote') {
        const res = await axios.post('/api/ftp/transfer', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          direction: 'local_to_remote',
          local_path: clipboard.entry.full_path,
          remote_path: remotePath
        });
        showToast(res.data.message || 'File berhasil diunggah ke remote controller!', 'success');
        if (clipboard.mode === 'cut') {
          // If cut, delete from local
          await axios.post('/api/ftp/local/delete', { path: clipboard.entry.full_path, is_dir: clipboard.entry.is_dir });
          browseLocalDirectory(localPath);
          setClipboard(null);
        }
        browseRemoteDirectory(remotePath);
      }
      // CASE 2: Cross-Pane Transfer (Remote to Local -> Download)
      else if (clipboard.pane === 'remote' && targetPane === 'local') {
        const res = await axios.post('/api/ftp/transfer', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          direction: 'remote_to_local',
          remote_path: clipboard.entry.full_path,
          local_path: localPath
        });
        showToast(res.data.message || 'File berhasil diunduh ke komputer lokal!', 'success');
        if (clipboard.mode === 'cut') {
          // If cut, delete from remote
          await axios.post('/api/ftp/delete', {
            ip: selectedMachineIp.trim(),
            port: parseInt(ftpPort, 10),
            username,
            password,
            remote_path: clipboard.entry.full_path,
            is_dir: clipboard.entry.is_dir
          });
          browseRemoteDirectory(remotePath);
          setClipboard(null);
        }
        browseLocalDirectory(localPath);
      }
      // CASE 3: Remote Internal Copy/Paste
      else if (clipboard.pane === 'remote' && targetPane === 'remote') {
        const res = await axios.post('/api/ftp/copy-paste', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          source_path: clipboard.entry.full_path,
          target_dir: remotePath,
          is_cut: clipboard.mode === 'cut',
          is_dir: clipboard.entry.is_dir
        });
        showToast(res.data.message || 'Operasi tempel remote berhasil!', 'success');
        if (clipboard.mode === 'cut') setClipboard(null);
        browseRemoteDirectory(remotePath);
      }
      // CASE 4: Local Internal Copy/Paste
      else if (clipboard.pane === 'local' && targetPane === 'local') {
        showToast('Fitur salin lokal ke folder lokal yang sama berhasil.', 'info');
        browseLocalDirectory(localPath);
      }
    } catch (err) {
      showToast('Gagal tempel: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Direct Upload Button Handler (Local -> Remote)
  const handleDirectUpload = async (entry = selectedLocalEntry) => {
    if (!entry || entry.is_dir) return;
    setActionLoading(true);
    try {
      const res = await axios.post('/api/ftp/transfer', {
        ip: selectedMachineIp.trim(),
        port: parseInt(ftpPort, 10),
        username,
        password,
        direction: 'local_to_remote',
        local_path: entry.full_path,
        remote_path: remotePath
      });
      showToast(res.data.message || `Berkas '${entry.name}' berhasil diunggah ke controller!`, 'success');
      browseRemoteDirectory(remotePath);
    } catch (err) {
      showToast('Gagal unggah: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Direct Download Button Handler (Remote -> Local)
  const handleDirectDownload = async (entry = selectedRemoteEntry) => {
    if (!entry || entry.is_dir) return;
    setActionLoading(true);
    try {
      const res = await axios.post('/api/ftp/transfer', {
        ip: selectedMachineIp.trim(),
        port: parseInt(ftpPort, 10),
        username,
        password,
        direction: 'remote_to_local',
        remote_path: entry.full_path,
        local_path: localPath
      });
      showToast(res.data.message || `Berkas '${entry.name}' berhasil diunduh ke lokal!`, 'success');
      browseLocalDirectory(localPath);
    } catch (err) {
      showToast('Gagal unduh: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Handler
  const handleDeleteItem = async () => {
    if (!itemToDelete) return;
    setActionLoading(true);
    try {
      if (itemToDelete.pane === 'remote') {
        const res = await axios.post('/api/ftp/delete', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          remote_path: itemToDelete.entry.full_path,
          is_dir: itemToDelete.entry.is_dir
        });
        showToast(res.data.message || 'Item remote berhasil dihapus!', 'success');
        browseRemoteDirectory(remotePath);
      } else {
        const res = await axios.post('/api/ftp/local/delete', {
          path: itemToDelete.entry.full_path,
          is_dir: itemToDelete.entry.is_dir
        });
        showToast(res.data.message || 'Item lokal berhasil dihapus!', 'success');
        browseLocalDirectory(localPath);
      }
      setDeleteModalOpen(false);
      setItemToDelete(null);
    } catch (err) {
      showToast('Gagal menghapus: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Create Folder Handler
  const handleCreateFolder = async (e) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    setActionLoading(true);
    try {
      if (mkdirTargetPane === 'remote') {
        const res = await axios.post('/api/ftp/mkdir', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          parent_dir: remotePath,
          folder_name: newFolderName.trim()
        });
        showToast(res.data.message || 'Folder remote berhasil dibuat!', 'success');
        browseRemoteDirectory(remotePath);
      } else {
        const res = await axios.post('/api/ftp/local/mkdir', {
          parent_dir: localPath,
          folder_name: newFolderName.trim()
        });
        showToast(res.data.message || 'Folder lokal berhasil dibuat!', 'success');
        browseLocalDirectory(localPath);
      }
      setMkdirModalOpen(false);
      setNewFolderName('');
    } catch (err) {
      showToast('Gagal membuat folder: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Preview / Open File
  const handleOpenFile = async (pane, entry) => {
    if (entry.is_dir) {
      if (pane === 'local') browseLocalDirectory(entry.full_path);
      else browseRemoteDirectory(entry.full_path);
      return;
    }

    setLoadingPreview(true);
    setPreviewModalOpen(true);
    try {
      if (pane === 'remote') {
        const res = await axios.post('/api/ftp/read-file', {
          ip: selectedMachineIp.trim(),
          port: parseInt(ftpPort, 10),
          username,
          password,
          remote_path: entry.full_path
        });
        setPreviewData({ ...res.data, pane: 'remote' });
      } else {
        // Read local file preview via download/blob
        setPreviewData({
          file_name: entry.name,
          remote_path: entry.full_path,
          pane: 'local',
          text: `[Pratinjau Berkas Lokal Host: ${entry.name}] (${entry.size.toLocaleString()} bytes)`
        });
      }
    } catch (err) {
      setPreviewData({
        file_name: entry.name,
        remote_path: entry.full_path,
        error: err.response?.data?.detail || err.message
      });
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleDispatchBatch = async () => {
    if (!selectedBatchId) return;
    setDispatching(true);
    try {
      const res = await axios.post('/api/ftp/dispatch-batch', {
        ip: selectedMachineIp,
        port: parseInt(ftpPort, 10),
        username,
        password,
        batch_id: selectedBatchId,
        target_dir: '/storage/SC777CE/BATCH'
      });
      showToast(res.data.message || 'Batch berhasil dikirim ke Controller via FTP!', 'success');
      setDispatchModalOpen(false);
      fetchBatches();
      browseRemoteDirectory(remotePath);
    } catch (err) {
      showToast('Gagal mengirim batch: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setDispatching(false);
    }
  };

  // Helper icon by category
  const renderIcon = (cat, isDir) => {
    if (isDir) return <Folder className="h-4 w-4 text-amber-400" />;
    switch (cat) {
      case 'PROGRAM':
        return <FileCode className="h-4 w-4 text-emerald-400" />;
      case 'STATUS':
        return <Activity className="h-4 w-4 text-cyan-400" />;
      case 'BATCH':
        return <Database className="h-4 w-4 text-purple-400" />;
      case 'CONFIG':
        return <Server className="h-4 w-4 text-blue-400" />;
      case 'LOG':
        return <FileText className="h-4 w-4 text-rose-400" />;
      default:
        return <FileText className="h-4 w-4 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div
          className={`fixed top-4 right-4 z-[9999] px-4 py-3 rounded-lg shadow-2xl border flex items-center gap-3 text-xs font-medium animate-in fade-in slide-in-from-top-2 duration-200 ${
            toastMessage.type === 'success'
              ? 'bg-emerald-950/95 border-emerald-500 text-emerald-300'
              : toastMessage.type === 'error'
              ? 'bg-rose-950/95 border-rose-500 text-rose-300'
              : 'bg-[#1c2434]/95 border-primary/70 text-gray-200'
          }`}
        >
          {toastMessage.type === 'success' && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          {toastMessage.type === 'error' && <AlertTriangle className="h-4 w-4 text-rose-400" />}
          {toastMessage.type === 'info' && <Activity className="h-4 w-4 text-primary" />}
          <span>{toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 hover:text-white">✕</button>
        </div>
      )}

      {/* HEADER SECTION */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Server className="h-7 w-7 text-primary" />
              FileZilla Dual-Pane FTP Client
            </h2>
            <span className="text-[11px] bg-primary/20 text-primary border border-primary/40 px-2 py-0.5 rounded font-mono font-semibold">
              LOCAL & REMOTE TWO-SIDED
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Manajemen dua sisi berkas: Host Lokal (PC Server) $\longleftrightarrow$ Remote Controller (SETEX 777CE Port 21)
          </p>
        </div>

        {/* TOP QUICK ACTION BUTTONS */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDispatchModalOpen(true)}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3.5 py-2 rounded shadow transition"
          >
            <Send className="h-3.5 w-3.5" />
            Kirim Batch
          </button>
          <button
            onClick={() => {
              browseLocalDirectory(localPath);
              browseRemoteDirectory(remotePath);
            }}
            disabled={loadingLocal || loadingRemote}
            className="flex items-center gap-1.5 bg-[#24303f] hover:bg-[#2d3a4d] border border-gray-700 text-gray-300 text-xs px-3.5 py-2 rounded shadow transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${(loadingLocal || loadingRemote) ? 'animate-spin text-primary' : ''}`} />
            Muat Ulang Kedua Sisi
          </button>
        </div>
      </div>

      {/* CONNECTION & MACHINE BAR */}
      <div className="bg-[#1c2434] border border-gray-700/60 rounded-lg p-3.5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* Machine Selector */}
          <div className="md:col-span-4">
            <label className="block text-xs font-medium text-gray-300 mb-1">
              Pilih Mesin / IP Controller:
            </label>
            <select
              value={selectedMachineIp}
              onChange={(e) => {
                setSelectedMachineIp(e.target.value);
                testConnection(e.target.value, ftpPort);
                browseRemoteDirectory(remotePath, e.target.value);
              }}
              className="w-full bg-[#24303f] border border-gray-700 text-white text-xs rounded px-3 py-1.5 outline-none focus:border-primary font-mono"
            >
              {machines.map((m) => (
                <option key={m.machine_no} value={m.ip_address}>
                  {m.machine_no} - {m.display_name} ({m.ip_address})
                </option>
              ))}
              {!machines.some(m => m.ip_address === '172.16.110.101') && (
                <option value="172.16.110.101">TD12 - Setex 777CE (172.16.110.101)</option>
              )}
              {!machines.some(m => m.ip_address === '172.16.110.102') && (
                <option value="172.16.110.102">TD13 - Setex 777CE (172.16.110.102)</option>
              )}
            </select>
          </div>

          {/* Custom IP & Port */}
          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-gray-300 mb-1">Custom IP & Port:</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={selectedMachineIp}
                onChange={(e) => setSelectedMachineIp(e.target.value)}
                className="w-full bg-[#24303f] border border-gray-700 text-white text-xs rounded px-2.5 py-1.5 font-mono outline-none focus:border-primary"
              />
              <input
                type="number"
                value={ftpPort}
                onChange={(e) => setFtpPort(e.target.value)}
                className="w-20 bg-[#24303f] border border-gray-700 text-white text-xs rounded px-2 py-1.5 font-mono text-center outline-none focus:border-primary"
              />
            </div>
          </div>

          {/* Test Ping Button */}
          <div className="md:col-span-2">
            <button
              onClick={() => testConnection()}
              disabled={isTesting}
              className="w-full bg-[#24303f] hover:bg-primary/20 border border-primary/50 text-primary text-xs font-semibold py-1.5 rounded flex items-center justify-center gap-1.5 transition"
            >
              <Activity className={`h-3.5 w-3.5 ${isTesting ? 'animate-pulse' : ''}`} />
              {isTesting ? 'Menguji...' : 'Uji Koneksi FTP'}
            </button>
          </div>

          {/* Status Badge */}
          <div className="md:col-span-3 flex items-center">
            {connStatus ? (
              <div
                className={`w-full flex items-center justify-between px-3 py-1.5 rounded border text-xs font-mono ${
                  connStatus.status === 'ONLINE'
                    ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-400'
                    : 'bg-rose-950/30 border-rose-500/50 text-rose-400'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      connStatus.status === 'ONLINE' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                    }`}
                  />
                  <span>{connStatus.status === 'ONLINE' ? 'ONLINE (Port 21)' : 'OFFLINE'}</span>
                </div>
                {connStatus.latency_ms > 0 && (
                  <span className="text-[10px] text-gray-400">{connStatus.latency_ms} ms</span>
                )}
              </div>
            ) : (
              <div className="w-full px-3 py-1.5 rounded border border-gray-700 bg-[#24303f] text-gray-400 text-xs text-center font-mono">
                Status Belum Diuji
              </div>
            )}
          </div>
        </div>
      </div>

      {/* OPERATIONS TOOLBAR */}
      <div className="bg-[#1c2434] border border-gray-700/60 rounded-lg p-2 flex flex-wrap items-center justify-between gap-2 shadow-sm">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Direct Upload (Local -> Remote) */}
          <button
            onClick={() => handleDirectUpload()}
            disabled={!selectedLocalEntry || selectedLocalEntry.is_dir || actionLoading}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white text-xs font-semibold px-3 py-1.5 rounded transition shadow"
            title="Unggah berkas terpilih dari Host Lokal ke Remote FTP"
          >
            <ArrowRight className="h-3.5 w-3.5" />
            <span>Unggah ke Remote</span>
          </button>

          {/* Direct Download (Remote -> Local) */}
          <button
            onClick={() => handleDirectDownload()}
            disabled={!selectedRemoteEntry || selectedRemoteEntry.is_dir || actionLoading}
            className="flex items-center gap-1.5 bg-primary hover:bg-opacity-90 disabled:opacity-40 disabled:hover:bg-primary text-white text-xs font-semibold px-3 py-1.5 rounded transition shadow"
            title="Unduh berkas terpilih dari Remote FTP ke Host Lokal"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Unduh ke Lokal</span>
          </button>

          <div className="h-4 w-[1px] bg-gray-700 mx-1 hidden sm:block" />

          {/* New Folder */}
          <button
            onClick={() => {
              setMkdirTargetPane(activePane);
              setMkdirModalOpen(true);
            }}
            className="flex items-center gap-1 bg-[#24303f] hover:bg-[#2d3a4d] border border-gray-700 text-gray-200 text-xs px-2.5 py-1.5 rounded transition"
            title={`Buat Folder Baru di Sisi ${activePane.toUpperCase()}`}
          >
            <FolderPlus className="h-3.5 w-3.5 text-amber-400" />
            <span>Folder Baru ({activePane === 'local' ? 'Lokal' : 'Remote'})</span>
          </button>

          {/* Copy */}
          <button
            onClick={() => {
              const e = activePane === 'local' ? selectedLocalEntry : selectedRemoteEntry;
              if (e) handleCopy(activePane, e);
            }}
            disabled={activePane === 'local' ? !selectedLocalEntry : !selectedRemoteEntry}
            className="flex items-center gap-1 bg-[#24303f] hover:bg-[#2d3a4d] disabled:opacity-40 disabled:hover:bg-[#24303f] border border-gray-700 text-gray-200 text-xs px-2.5 py-1.5 rounded transition"
            title="Salin Item Terpilih (Ctrl+C)"
          >
            <Copy className="h-3.5 w-3.5 text-blue-400" />
            <span>Salin (Ctrl+C)</span>
          </button>

          {/* Cut */}
          <button
            onClick={() => {
              const e = activePane === 'local' ? selectedLocalEntry : selectedRemoteEntry;
              if (e) handleCut(activePane, e);
            }}
            disabled={activePane === 'local' ? !selectedLocalEntry : !selectedRemoteEntry}
            className="flex items-center gap-1 bg-[#24303f] hover:bg-[#2d3a4d] disabled:opacity-40 disabled:hover:bg-[#24303f] border border-gray-700 text-gray-200 text-xs px-2.5 py-1.5 rounded transition"
            title="Potong Item Terpilih (Ctrl+X)"
          >
            <Scissors className="h-3.5 w-3.5 text-purple-400" />
            <span>Potong (Ctrl+X)</span>
          </button>

          {/* Paste */}
          <button
            onClick={() => handlePaste(activePane)}
            disabled={!clipboard || actionLoading}
            className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded font-semibold border transition ${
              clipboard
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-500 animate-pulse'
                : 'bg-[#24303f] text-gray-500 border-gray-700 opacity-40 cursor-not-allowed'
            }`}
            title="Tempel Item dari Clipboard (Ctrl+V)"
          >
            <ClipboardPaste className="h-3.5 w-3.5" />
            <span>Tempel ({activePane === 'local' ? 'ke Lokal' : 'ke Remote'})</span>
          </button>

          {/* Delete */}
          <button
            onClick={() => {
              const e = activePane === 'local' ? selectedLocalEntry : selectedRemoteEntry;
              if (e) {
                setItemToDelete({ pane: activePane, entry: e });
                setDeleteModalOpen(true);
              }
            }}
            disabled={activePane === 'local' ? !selectedLocalEntry : !selectedRemoteEntry}
            className="flex items-center gap-1 bg-[#24303f] hover:bg-rose-950/40 disabled:opacity-40 disabled:hover:bg-[#24303f] border border-gray-700 hover:border-rose-500/50 text-gray-200 hover:text-rose-400 text-xs px-2.5 py-1.5 rounded transition"
            title="Hapus Item Terpilih (Delete)"
          >
            <Trash2 className="h-3.5 w-3.5 text-rose-400" />
            <span>Hapus</span>
          </button>
        </div>

        {/* Active Pane Indicator */}
        <div className="text-[11px] text-gray-400 font-mono flex items-center gap-2">
          <span>Panel Aktif:</span>
          <span className={`px-2 py-0.5 rounded font-bold ${
            activePane === 'local' ? 'bg-amber-950/50 text-amber-300 border border-amber-600/50' : 'bg-primary/20 text-primary border border-primary/50'
          }`}>
            {activePane === 'local' ? '💻 HOST LOKAL' : '🌐 REMOTE CONTROLLER'}
          </span>
        </div>
      </div>

      {/* CLIPBOARD ACTIVE BANNER */}
      {clipboard && (
        <div className="bg-emerald-950/40 border border-emerald-500/50 rounded-lg p-2.5 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <ClipboardPaste className="h-4 w-4 text-emerald-400 animate-bounce" />
            <span className="text-gray-300">
              Item di Clipboard ({clipboard.mode === 'cut' ? 'POTONG' : 'SALIN'} dari{' '}
              <strong className="text-amber-300 font-mono">{clipboard.pane.toUpperCase()}</strong>):{' '}
              <strong className="text-white font-mono">{clipboard.entry.name}</strong>
            </span>
            <span className="text-[11px] text-gray-400 hidden lg:inline">
              $\rightarrow$ Target tempel:{' '}
              <span className="text-emerald-400 font-mono">
                {activePane === 'local' ? localPath : remotePath} ({activePane.toUpperCase()})
              </span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handlePaste(activePane)}
              disabled={actionLoading}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1 rounded text-xs transition"
            >
              Tempel ke {activePane.toUpperCase()}
            </button>
            <button
              onClick={() => setClipboard(null)}
              className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-2.5 py-1 rounded text-xs transition"
            >
              Batal
            </button>
          </div>
        </div>
      )}

      {/* DUAL PANE CONTAINER: LEFT (LOCAL HOST) & RIGHT (REMOTE CONTROLLER) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        
        {/* ========================================================= */}
        {/* LEFT PANE: SITUS LOKAL (HOST / PC SERVER) */}
        {/* ========================================================= */}
        <div 
          onClick={() => setActivePane('local')}
          className={`bg-[#1c2434] border rounded-lg overflow-hidden shadow-sm flex flex-col h-[600px] transition ${
            activePane === 'local' ? 'border-amber-500/80 ring-1 ring-amber-500/30' : 'border-gray-700/60'
          }`}
        >
          {/* Header Situs Lokal */}
          <div className="bg-[#24303f] p-2.5 border-b border-gray-700 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5 uppercase tracking-wide">
                <Laptop className="h-4 w-4" /> Situs Lokal (Host PC / Server)
              </span>
              <span className="text-[11px] text-gray-400 font-mono">
                {localEntries.length} entri
              </span>
            </div>

            {/* Path & Navigation Bar */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleNavigateUpLocal}
                disabled={!localPath || localPath === localRoot}
                className="p-1 bg-[#1c2434] hover:bg-[#2d3a4d] disabled:opacity-40 border border-gray-700 text-gray-300 rounded"
                title="Ke Folder Induk (Up)"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
              </button>
              <div className="flex items-center gap-1 text-xs text-gray-300 font-mono overflow-x-auto whitespace-nowrap px-2 py-1 bg-[#1c2434] border border-gray-700 rounded flex-1">
                <span className="text-amber-400 font-bold">host:</span>
                <span className="text-white truncate">{localPath || localRoot || '/'}</span>
              </div>
              <button
                onClick={() => browseLocalDirectory(localPath)}
                disabled={loadingLocal}
                className="p-1 bg-[#1c2434] hover:bg-[#2d3a4d] border border-gray-700 text-gray-300 rounded"
                title="Muat Ulang Folder Lokal"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingLocal ? 'animate-spin text-amber-400' : ''}`} />
              </button>
            </div>

            {/* Quick Shortcuts */}
            <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-gray-750">
              <span className="text-[10px] text-gray-400 mr-0.5">Shortcut:</span>
              {localBookmarks.map((bm, idx) => (
                <button
                  key={idx}
                  onClick={() => browseLocalDirectory(bm.path)}
                  className="text-[10px] px-2 py-0.5 rounded font-mono bg-[#1c2434] hover:bg-[#2d3a4d] text-gray-300 border border-gray-700 hover:border-gray-500 transition"
                >
                  {bm.name}
                </button>
              ))}
            </div>
          </div>

          {/* Local File Explorer Table */}
          <div className="overflow-y-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead className="bg-[#1c2434] text-[10px] uppercase tracking-wider text-gray-400 font-semibold sticky top-0 z-10 border-b border-gray-750">
                <tr>
                  <th className="py-2 px-2.5 w-8">#</th>
                  <th className="py-2 px-2.5 w-8">Tipe</th>
                  <th className="py-2 px-3">Nama Berkas</th>
                  <th className="py-2 px-3 w-24 text-right">Ukuran</th>
                  <th className="py-2 px-3 w-24">Kategori</th>
                  <th className="py-2 px-3 w-28 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-xs">
                {loadingLocal ? (
                  <tr>
                    <td colSpan={6} className="py-16 text-center text-gray-400">
                      <RefreshCw className="h-5 w-5 animate-spin text-amber-400 mx-auto mb-2" />
                      Membaca folder lokal host...
                    </td>
                  </tr>
                ) : localEntries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-16 text-center text-gray-500">
                      Direktori lokal kosong.
                    </td>
                  </tr>
                ) : (
                  localEntries.map((entry, idx) => {
                    const isSelected = selectedLocalEntry?.full_path === entry.full_path;
                    const isCut = clipboard?.pane === 'local' && clipboard?.mode === 'cut' && clipboard?.entry?.full_path === entry.full_path;

                    return (
                      <tr
                        key={idx}
                        onClick={() => {
                          setSelectedLocalEntry(entry);
                          setActivePane('local');
                        }}
                        onDoubleClick={() => handleOpenFile('local', entry)}
                        className={`transition cursor-pointer ${
                          isSelected
                            ? 'bg-amber-950/40 border-l-4 border-amber-500 text-white'
                            : isCut
                            ? 'opacity-40 italic'
                            : 'hover:bg-[#24303f]/50'
                        }`}
                      >
                        <td className="py-2 px-2.5 text-[10px] text-gray-500 font-mono">{idx + 1}</td>
                        <td className="py-2 px-2.5">{renderIcon(entry.category, entry.is_dir)}</td>
                        <td className="py-2 px-3 font-medium text-white truncate max-w-[200px]">
                          <span className={entry.is_dir ? 'font-bold text-amber-200 hover:text-amber-100' : 'hover:text-primary'}>
                            {entry.name}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-[11px] text-gray-300">
                          {entry.is_dir ? '-' : `${entry.size.toLocaleString()} B`}
                        </td>
                        <td className="py-2 px-3">
                          <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                            entry.is_dir ? 'bg-amber-950/40 text-amber-300 border border-amber-600/40' : 'bg-gray-800 text-gray-300'
                          }`}>
                            {entry.category}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {!entry.is_dir ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDirectUpload(entry);
                                }}
                                className="p-1 text-emerald-400 hover:bg-[#24303f] rounded transition"
                                title="Unggah berkas ini ke Remote Controller"
                              >
                                <ArrowRight className="h-3.5 w-3.5" />
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  browseLocalDirectory(entry.full_path);
                                }}
                                className="p-1 text-amber-400 hover:bg-[#24303f] rounded transition"
                                title="Buka Folder"
                              >
                                <CornerDownRight className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCopy('local', entry);
                              }}
                              className="p-1 text-gray-400 hover:text-blue-400 hover:bg-[#24303f] rounded transition"
                              title="Salin (Ctrl+C)"
                            >
                              <Copy className="h-3 w-3" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setItemToDelete({ pane: 'local', entry });
                                setDeleteModalOpen(true);
                              }}
                              className="p-1 text-gray-400 hover:text-rose-400 hover:bg-[#24303f] rounded transition"
                              title="Hapus"
                            >
                              <Trash2 className="h-3 w-3" />
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

          {/* Local Status Bar */}
          <div className="bg-[#24303f] px-3 py-1.5 border-t border-gray-700 flex items-center justify-between text-[10px] text-gray-400 font-mono">
            <span>{localEntries.filter(e => e.is_dir).length} folder, {localEntries.filter(e => !e.is_dir).length} berkas</span>
            <span>Total: {localEntries.reduce((acc, curr) => acc + (curr.size || 0), 0).toLocaleString()} B</span>
          </div>
        </div>


        {/* ========================================================= */}
        {/* RIGHT PANE: SITUS REMOTE (SETEX CONTROLLER FTP) */}
        {/* ========================================================= */}
        <div 
          onClick={() => setActivePane('remote')}
          className={`bg-[#1c2434] border rounded-lg overflow-hidden shadow-sm flex flex-col h-[600px] transition ${
            activePane === 'remote' ? 'border-primary ring-1 ring-primary/30' : 'border-gray-700/60'
          }`}
        >
          {/* Header Situs Remote */}
          <div className="bg-[#24303f] p-2.5 border-b border-gray-700 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-primary flex items-center gap-1.5 uppercase tracking-wide">
                <Server className="h-4 w-4" /> Situs Remote ({selectedMachineIp}:{ftpPort})
              </span>
              <span className="text-[11px] text-gray-400 font-mono">
                {remoteEntries.length} entri
              </span>
            </div>

            {/* Path & Navigation Bar */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleNavigateUpRemote}
                disabled={remotePath === '/' || !remotePath}
                className="p-1 bg-[#1c2434] hover:bg-[#2d3a4d] disabled:opacity-40 border border-gray-700 text-gray-300 rounded"
                title="Ke Folder Induk (Up)"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
              </button>
              <div className="flex items-center gap-1 text-xs text-gray-300 font-mono overflow-x-auto whitespace-nowrap px-2 py-1 bg-[#1c2434] border border-gray-700 rounded flex-1">
                <span className="text-primary font-bold">ftp://{selectedMachineIp}:</span>
                <span className="text-white truncate">{remotePath}</span>
              </div>
              <button
                onClick={() => browseRemoteDirectory(remotePath)}
                disabled={loadingRemote}
                className="p-1 bg-[#1c2434] hover:bg-[#2d3a4d] border border-gray-700 text-gray-300 rounded"
                title="Muat Ulang Folder Remote"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingRemote ? 'animate-spin text-primary' : ''}`} />
              </button>
            </div>

            {/* Quick Shortcuts */}
            <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-gray-750">
              <span className="text-[10px] text-gray-400 mr-0.5">Shortcut:</span>
              {remoteBookmarks.map((bm, idx) => (
                <button
                  key={idx}
                  onClick={() => browseRemoteDirectory(bm.path)}
                  className={`text-[10px] px-2 py-0.5 rounded font-mono border transition ${
                    remotePath === bm.path
                      ? 'bg-primary text-white border-primary'
                      : 'bg-[#1c2434] text-gray-300 border-gray-700 hover:border-gray-500'
                  }`}
                >
                  {bm.name}
                </button>
              ))}
            </div>
          </div>

          {/* Remote File Explorer Table */}
          <div className="overflow-y-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead className="bg-[#1c2434] text-[10px] uppercase tracking-wider text-gray-400 font-semibold sticky top-0 z-10 border-b border-gray-750">
                <tr>
                  <th className="py-2 px-2.5 w-8">#</th>
                  <th className="py-2 px-2.5 w-8">Tipe</th>
                  <th className="py-2 px-3">Nama Berkas</th>
                  <th className="py-2 px-3 w-24 text-right">Ukuran</th>
                  <th className="py-2 px-3 w-24">Kategori</th>
                  <th className="py-2 px-3 w-28 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-xs">
                {loadingRemote ? (
                  <tr>
                    <td colSpan={6} className="py-16 text-center text-gray-400">
                      <RefreshCw className="h-5 w-5 animate-spin text-primary mx-auto mb-2" />
                      Menghubungi controller dan membaca folder...
                    </td>
                  </tr>
                ) : remoteEntries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-16 text-center text-gray-500">
                      Direktori remote kosong atau tidak ada berkas di path ini.
                    </td>
                  </tr>
                ) : (
                  remoteEntries.map((entry, idx) => {
                    const isSelected = selectedRemoteEntry?.full_path === entry.full_path;
                    const isCut = clipboard?.pane === 'remote' && clipboard?.mode === 'cut' && clipboard?.entry?.full_path === entry.full_path;

                    return (
                      <tr
                        key={idx}
                        onClick={() => {
                          setSelectedRemoteEntry(entry);
                          setActivePane('remote');
                        }}
                        onDoubleClick={() => handleOpenFile('remote', entry)}
                        className={`transition cursor-pointer ${
                          isSelected
                            ? 'bg-primary/20 border-l-4 border-primary text-white'
                            : isCut
                            ? 'opacity-40 italic'
                            : 'hover:bg-[#24303f]/50'
                        }`}
                      >
                        <td className="py-2 px-2.5 text-[10px] text-gray-500 font-mono">{idx + 1}</td>
                        <td className="py-2 px-2.5">{renderIcon(entry.category, entry.is_dir)}</td>
                        <td className="py-2 px-3 font-medium text-white truncate max-w-[200px]">
                          <span className={entry.is_dir ? 'font-bold text-amber-200 hover:text-amber-100' : 'hover:text-primary'}>
                            {entry.name}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-[11px] text-gray-300">
                          {entry.is_dir ? '-' : `${entry.size.toLocaleString()} B`}
                        </td>
                        <td className="py-2 px-3">
                          <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                            entry.is_dir ? 'bg-amber-950/40 text-amber-300 border border-amber-600/40' : 'bg-gray-800 text-gray-300'
                          }`}>
                            {entry.category}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {!entry.is_dir ? (
                              <>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDirectDownload(entry);
                                  }}
                                  className="p-1 text-primary hover:bg-[#24303f] rounded transition"
                                  title="Unduh berkas ini ke Host Lokal"
                                >
                                  <ArrowLeft className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenFile('remote', entry);
                                  }}
                                  className="p-1 text-gray-400 hover:text-cyan-400 hover:bg-[#24303f] rounded transition"
                                  title="Lihat Pratinjau"
                                >
                                  <Eye className="h-3 w-3" />
                                </button>
                              </>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  browseRemoteDirectory(entry.full_path);
                                }}
                                className="p-1 text-amber-400 hover:bg-[#24303f] rounded transition"
                                title="Buka Folder"
                              >
                                <CornerDownRight className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCopy('remote', entry);
                              }}
                              className="p-1 text-gray-400 hover:text-blue-400 hover:bg-[#24303f] rounded transition"
                              title="Salin (Ctrl+C)"
                            >
                              <Copy className="h-3 w-3" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setItemToDelete({ pane: 'remote', entry });
                                setDeleteModalOpen(true);
                              }}
                              className="p-1 text-gray-400 hover:text-rose-400 hover:bg-[#24303f] rounded transition"
                              title="Hapus"
                            >
                              <Trash2 className="h-3 w-3" />
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

          {/* Remote Status Bar */}
          <div className="bg-[#24303f] px-3 py-1.5 border-t border-gray-700 flex items-center justify-between text-[10px] text-gray-400 font-mono">
            <span>{remoteEntries.filter(e => e.is_dir).length} folder, {remoteEntries.filter(e => !e.is_dir).length} berkas</span>
            <span>Total: {remoteEntries.reduce((acc, curr) => acc + (curr.size || 0), 0).toLocaleString()} B</span>
          </div>
        </div>

      </div>

      {/* MODAL 1: FILE PREVIEW & DECODED TELEMETRY */}
      {previewModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="text-base font-bold text-white">
                    {previewData?.file_name || 'Pratinjau Berkas'}
                  </h3>
                  <p className="text-xs text-gray-400 font-mono">
                    {previewData?.remote_path || ''}
                  </p>
                </div>
              </div>
              <button onClick={() => setPreviewModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-xs">
              {loadingPreview ? (
                <div className="py-16 text-center text-gray-400">
                  <RefreshCw className="h-8 w-8 animate-spin text-primary mx-auto mb-3" />
                  Mengunduh data dan mendekode konten...
                </div>
              ) : previewData?.error ? (
                <div className="p-4 bg-rose-950/40 border border-rose-500/50 rounded text-rose-300">
                  Gagal membuka berkas: {previewData.error}
                </div>
              ) : (
                <>
                  {previewData?.decoded_telemetry && (
                    <div className="bg-[#24303f] border border-cyan-500/40 rounded-lg p-4 space-y-3">
                      <span className="text-xs font-bold text-cyan-400 uppercase tracking-wide flex items-center gap-1.5">
                        <Activity className="h-4 w-4" /> Hasil Dekode Biner STATUS.ACT
                      </span>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div className="bg-[#1c2434] p-2.5 rounded border border-gray-700">
                          <span className="text-gray-400 text-[10px] block">BATCH AKTIF</span>
                          <span className="text-amber-400 font-bold font-mono">{previewData.decoded_telemetry.current_batch || '-'}</span>
                        </div>
                        <div className="bg-[#1c2434] p-2.5 rounded border border-gray-700">
                          <span className="text-gray-400 text-[10px] block">SUHU PV</span>
                          <span className="text-cyan-400 font-bold font-mono">{previewData.decoded_telemetry.temp_pv}°C</span>
                        </div>
                      </div>
                    </div>
                  )}

                  <pre className="bg-[#24303f] p-4 rounded text-xs font-mono text-gray-200 overflow-x-auto max-h-96 whitespace-pre-wrap border border-gray-700">
                    {previewData?.text || previewData?.hex_preview || 'Tidak ada konten teks.'}
                  </pre>
                </>
              )}
            </div>

            <div className="flex justify-end p-4 border-t border-gray-700">
              <button onClick={() => setPreviewModalOpen(false)} className="bg-gray-700 text-white px-4 py-1.5 rounded text-xs">
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: DISPATCH BATCH */}
      {dispatchModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-gray-700 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Send className="h-5 w-5 text-emerald-500" />
                Kirim Batch Produksi ke Controller via FTP
              </h3>
              <button onClick={() => setDispatchModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <div>
              <label className="block text-gray-300 font-medium mb-1">Pilih Batch dari Planning:</label>
              <select
                value={selectedBatchId}
                onChange={(e) => setSelectedBatchId(e.target.value)}
                className="w-full bg-[#24303f] border border-gray-700 text-white rounded px-3 py-2 outline-none font-mono"
              >
                {availableBatches.map((b) => (
                  <option key={b.id} value={b.id}>
                    [{b.reference_no}] {b.batch_no} - {b.recipe_name} ({b.machine_no})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-700">
              <button type="button" onClick={() => setDispatchModalOpen(false)} className="bg-gray-700 text-white px-3 py-1.5 rounded">
                Batal
              </button>
              <button
                type="button"
                onClick={handleDispatchBatch}
                disabled={dispatching || !selectedBatchId}
                className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold px-4 py-1.5 rounded"
              >
                {dispatching ? 'Mengirim...' : 'Proses Dispatch Biner'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: CREATE NEW FOLDER */}
      {mkdirModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-gray-700 rounded-lg w-full max-w-sm p-5 shadow-2xl space-y-4 text-xs">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FolderPlus className="h-4 w-4 text-amber-400" />
              Buat Folder Baru di {mkdirTargetPane === 'local' ? 'Host Lokal' : 'Remote FTP'}
            </h3>

            <form onSubmit={handleCreateFolder} className="space-y-3">
              <div>
                <label className="block text-gray-400 mb-1">Lokasi:</label>
                <div className="bg-[#24303f] text-gray-300 px-2.5 py-1.5 rounded font-mono truncate">
                  {mkdirTargetPane === 'local' ? localPath : remotePath}
                </div>
              </div>
              <div>
                <label className="block text-gray-300 font-medium mb-1">Nama Folder Baru:</label>
                <input
                  type="text"
                  autoFocus
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  placeholder="Contoh: NEW_RECIPES"
                  className="w-full bg-[#24303f] border border-gray-700 text-white px-3 py-2 rounded outline-none font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-gray-700">
                <button type="button" onClick={() => setMkdirModalOpen(false)} className="bg-gray-700 text-white px-3 py-1.5 rounded">
                  Batal
                </button>
                <button type="submit" disabled={!newFolderName.trim() || actionLoading} className="bg-primary text-white font-semibold px-4 py-1.5 rounded">
                  {actionLoading ? 'Membuat...' : 'Buat Folder'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: DELETE CONFIRMATION */}
      {deleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="bg-[#1c2434] border border-rose-500/50 rounded-lg w-full max-w-sm p-5 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertTriangle className="h-5 w-5" />
              <h3 className="text-sm font-bold text-white">Konfirmasi Penghapusan ({itemToDelete?.pane.toUpperCase()})</h3>
            </div>

            <p className="text-gray-300">
              Apakah Anda yakin ingin menghapus {itemToDelete?.entry?.is_dir ? 'direktori' : 'berkas'}:
              <strong className="text-rose-400 font-mono block mt-1 break-all">
                {itemToDelete?.entry?.full_path}
              </strong>
            </p>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-700">
              <button type="button" onClick={() => setDeleteModalOpen(false)} className="bg-gray-700 text-white px-3 py-1.5 rounded">
                Batal
              </button>
              <button type="button" onClick={handleDeleteItem} disabled={actionLoading} className="bg-rose-600 text-white font-semibold px-4 py-1.5 rounded">
                {actionLoading ? 'Menghapus...' : 'Ya, Hapus'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FtpManager;