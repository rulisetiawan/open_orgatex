import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getApiErrorMessage } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import useVisibilityInterval from '../../hooks/useVisibilityInterval';
import {
  WifiOff,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Search,
  Download,
  Server,
  Clock,
  ExternalLink,
  Filter,
  ShieldAlert,
  HelpCircle,
} from 'lucide-react';

const STATUS_BADGE = {
  FAILED: {
    label: 'Gagal Baca FTP',
    cls: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30',
    icon: XCircle,
  },
  PARTIAL: {
    label: 'STATUS.ACT Tidak Terbaca',
    cls: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30',
    icon: AlertTriangle,
  },
  PENDING: {
    label: 'Menunggu Siklus Worker',
    cls: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-meta-4 dark:text-bodydark dark:border-strokedark',
    icon: HelpCircle,
  },
  OK: {
    label: 'FTP Normal',
    cls: 'bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/30',
    icon: CheckCircle2,
  },
};

const CATEGORY_LABELS = {
  OK: 'Normal',
  FTP_421_TOO_MANY_CONN: 'FTP 421 (Koneksi Penuh)',
  FTP_429_TOO_MANY_CONN: 'FTP 429 (Limit Koneksi)',
  FTP_LOGIN_FAILED: 'FTP 530 (Login Ditolak)',
  FTP_REFUSED: 'Port 21 Ditolak',
  FTP_TIMEOUT: 'FTP Timeout',
  FTP_OFFLINE_OR_TIMEOUT: 'Offline / Timeout',
  FTP_ERROR: 'Error FTP',
  FTP_NO_DATA: 'Gagal Login / Kosong',
  STATUS_ACT_NOT_FOUND: 'STATUS.ACT Tidak Ada',
  NO_WORKER_DATA: 'Belum Dicek Worker',
};

const formatDateTime = (iso) => {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '-';
  }
};

const FtpHealthMonitor = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [machines, setMachines] = useState([]);
  const [summary, setSummary] = useState({
    total_machines: 0,
    ftp_ok_count: 0,
    ftp_partial_count: 0,
    ftp_failed_count: 0,
    ftp_pending_count: 0,
    ftp_unreadable_count: 0,
  });
  const [lastCycleAt, setLastCycleAt] = useState(null);
  const [workerName, setWorkerName] = useState('DA-Batch-Worker-24x7');
  const [loading, setLoading] = useState(false);

  // Filter default: langsung tampilkan mesin yang tidak bisa baca FTP
  const [statusFilter, setStatusFilter] = useState('UNREADABLE'); // UNREADABLE | PENDING | OK | ALL
  const [groupFilter, setGroupFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [includeInactive, setIncludeInactive] = useState(false);

  const fetchWorkerStatus = useCallback(
    async (customIncludeInactive = includeInactive, silent = false) => {
      if (!silent) setLoading(true);
      try {
        const res = await api.get('/ftp/worker-status', {
          params: { include_inactive: customIncludeInactive },
        });
        const data = res.data || {};
        setMachines(data.machines || []);
        setSummary(
          data.summary || {
            total_machines: 0,
            ftp_ok_count: 0,
            ftp_partial_count: 0,
            ftp_failed_count: 0,
            ftp_pending_count: 0,
            ftp_unreadable_count: 0,
          }
        );
        setLastCycleAt(data.last_cycle_at || null);
        if (data.worker_name) setWorkerName(data.worker_name);
      } catch (err) {
        if (!silent) {
          toast?.error?.(getApiErrorMessage(err, 'Gagal memuat status FTP dari da-batch-worker.'));
        }
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [includeInactive, toast]
  );

  useEffect(() => {
    fetchWorkerStatus(includeInactive, false);
  }, [fetchWorkerStatus, includeInactive]);

  // Auto-refresh dari database setiap 30 detik (tanpa membuka koneksi FTP baru ke mesin)
  useVisibilityInterval(() => {
    fetchWorkerStatus(includeInactive, true);
  }, 30000);

  const groups = useMemo(() => {
    const set = new Set();
    machines.forEach((m) => {
      if (m.group_name) set.add(m.group_name);
    });
    return ['ALL', ...Array.from(set).sort()];
  }, [machines]);

  const filteredMachines = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return machines.filter((m) => {
      if (statusFilter === 'UNREADABLE' && !['FAILED', 'PARTIAL'].includes(m.ftp_status)) return false;
      if (statusFilter === 'PENDING' && m.ftp_status !== 'PENDING') return false;
      if (statusFilter === 'OK' && m.ftp_status !== 'OK') return false;
      if (groupFilter !== 'ALL' && m.group_name !== groupFilter) return false;
      if (q) {
        const hay = `${m.machine_no} ${m.display_name} ${m.ip_address} ${m.group_name} ${m.error_detail} ${m.failure_category}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [machines, statusFilter, groupFilter, searchTerm]);

  const handleExportCsv = () => {
    if (!filteredMachines.length) {
      toast?.info?.('Tidak ada data untuk diekspor.');
      return;
    }
    const headers = [
      'Mesin',
      'Nama',
      'Grup',
      'IP Address',
      'FTP Port',
      'Status FTP',
      'Kategori',
      'Gagal Berturut-turut',
      'Batch Aktif',
      'Latency (ms)',
      'Terakhir Dicek Worker',
      'Terakhir Berhasil FTP',
      'Detail Error',
    ];
    const escapeCsv = (val) => `"${String(val ?? '').replace(/"/g, '""')}"`;
    const rows = filteredMachines.map((m) =>
      [
        m.machine_no,
        m.display_name,
        m.group_name,
        m.ip_address,
        m.ftp_port,
        m.ftp_status,
        CATEGORY_LABELS[m.failure_category] || m.failure_category,
        m.consecutive_failures,
        m.active_batch || '-',
        m.latency_ms,
        formatDateTime(m.last_checked_at),
        formatDateTime(m.last_success_at),
        m.error_detail,
      ]
        .map(escapeCsv)
        .join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `status_ftp_batch_worker_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      {/* HEADER */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/10 text-red-600 dark:text-red-400">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-black dark:text-white tracking-tight">
              Status Baca FTP Mesin
            </h1>
            <p className="text-xs text-body dark:text-bodydark">
              Data diambil langsung dari laporan siklus <code className="font-mono font-semibold">{workerName}</code> di database — tanpa membuka koneksi FTP tambahan ke kontroler.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <label className="flex items-center gap-1.5 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark px-2.5 py-1.5 text-xs text-body dark:text-bodydark cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
              className="rounded border-stroke accent-primary"
            />
            <span>Sertakan non-aktif</span>
          </label>

          <button
            type="button"
            onClick={handleExportCsv}
            disabled={loading || filteredMachines.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark px-3 py-2 text-xs font-semibold text-black dark:text-white hover:bg-gray dark:hover:bg-meta-4 transition disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>

          <button
            type="button"
            onClick={() => fetchWorkerStatus(includeInactive, false)}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-primary/90 transition disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Memuat...' : 'Refresh Data'}
          </button>
        </div>
      </div>

      {/* SUMMARY KPI CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <button
          type="button"
          onClick={() => setStatusFilter('UNREADABLE')}
          className={`text-left rounded-xl border p-4 transition ${
            statusFilter === 'UNREADABLE'
              ? 'border-red-500 bg-red-50/70 dark:bg-red-500/10 ring-1 ring-red-500/40'
              : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-red-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
              Tidak Bisa Baca FTP
            </span>
            <WifiOff className="h-4 w-4 text-red-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-red-600 dark:text-red-400">
              {summary.ftp_unreadable_count}
            </span>
            <span className="text-[11px] text-body dark:text-bodydark">
              ({summary.ftp_failed_count} gagal, {summary.ftp_partial_count} tanpa STATUS.ACT)
            </span>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter('OK')}
          className={`text-left rounded-xl border p-4 transition ${
            statusFilter === 'OK'
              ? 'border-emerald-500 bg-emerald-50/70 dark:bg-emerald-500/10 ring-1 ring-emerald-500/40'
              : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-emerald-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
              FTP Normal
            </span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {summary.ftp_ok_count}
            </span>
            <span className="text-[11px] text-body dark:text-bodydark">
              STATUS.ACT terbaca lancar
            </span>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter('PENDING')}
          className={`text-left rounded-xl border p-4 transition ${
            statusFilter === 'PENDING'
              ? 'border-amber-500 bg-amber-50/70 dark:bg-amber-500/10 ring-1 ring-amber-500/40'
              : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
              Belum Dicek Worker
            </span>
            <HelpCircle className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {summary.ftp_pending_count}
            </span>
            <span className="text-[11px] text-body dark:text-bodydark">
              Menunggu siklus da-batch-worker
            </span>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter('ALL')}
          className={`text-left rounded-xl border p-4 transition ${
            statusFilter === 'ALL'
              ? 'border-primary bg-primary/5 dark:bg-primary/10 ring-1 ring-primary/40'
              : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-primary/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-body dark:text-bodydark">
              Total Mesin
            </span>
            <Server className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-black dark:text-white">
              {summary.total_machines}
            </span>
            <span className="text-[11px] text-body dark:text-bodydark flex items-center gap-1 truncate">
              <Clock className="h-3 w-3 shrink-0" />
              {formatDateTime(lastCycleAt)}
            </span>
          </div>
        </button>
      </div>

      {/* FILTER BAR */}
      <div className="rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: 'UNREADABLE', label: `Tidak Bisa Baca FTP (${summary.ftp_unreadable_count})` },
            { id: 'PENDING', label: `Belum Dicek (${summary.ftp_pending_count})` },
            { id: 'OK', label: `FTP Normal (${summary.ftp_ok_count})` },
            { id: 'ALL', label: `Semua (${summary.total_machines})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                statusFilter === tab.id
                  ? 'bg-primary text-white shadow-xs'
                  : 'bg-gray dark:bg-meta-4/50 text-body dark:text-bodydark hover:text-black dark:hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-stroke dark:border-strokedark px-2.5 py-1.5 text-xs bg-transparent">
            <Filter className="h-3.5 w-3.5 text-body dark:text-bodydark" />
            <select
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
              className="bg-transparent text-black dark:text-white focus:outline-none"
            >
              {groups.map((g) => (
                <option key={g} value={g} className="dark:bg-boxdark">
                  {g === 'ALL' ? 'Semua Section' : g}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Search className="h-3.5 w-3.5 text-body dark:text-bodydark absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Cari mesin, IP, error..."
              className="w-52 rounded-lg border border-stroke dark:border-strokedark bg-transparent pl-8 pr-3 py-1.5 text-xs text-black dark:text-white placeholder:text-bodydark2 focus:border-primary focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* RESULTS TABLE */}
      <div className="rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-stroke dark:border-strokedark bg-gray-2/60 dark:bg-meta-4/40 text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark">
                <th className="py-3 px-4">Mesin</th>
                <th className="py-3 px-4">IP &amp; Port</th>
                <th className="py-3 px-4">Status Baca FTP</th>
                <th className="py-3 px-4">Gagal Berturut</th>
                <th className="py-3 px-4">Terakhir Dicek / Sukses</th>
                <th className="py-3 px-4">Penyebab / Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke dark:divide-strokedark text-xs">
              {loading && machines.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-body dark:text-bodydark">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
                    Memuat status FTP terbaru dari <code className="font-mono">da-batch-worker</code>...
                  </td>
                </tr>
              ) : filteredMachines.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-body dark:text-bodydark">
                    {statusFilter === 'UNREADABLE' && summary.total_machines > 0 && summary.ftp_unreadable_count === 0 ? (
                      summary.ftp_pending_count === summary.total_machines ? (
                        <div className="flex flex-col items-center gap-1.5 text-amber-600 dark:text-amber-400">
                          <HelpCircle className="h-7 w-7" />
                          <p className="font-semibold">Belum ada laporan siklus dari da-batch-worker.</p>
                          <p className="text-[11px] text-body dark:text-bodydark">
                            Restart service <code className="font-mono">da-batch-worker</code> lalu tunggu 1 siklus selesai.
                          </p>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center gap-2 text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="h-8 w-8" />
                          <p className="font-semibold">Tidak ada mesin yang gagal baca FTP pada siklus terakhir!</p>
                        </div>
                      )
                    ) : (
                      <p>Tidak ada mesin yang cocok dengan filter saat ini.</p>
                    )}
                  </td>
                </tr>
              ) : (
                filteredMachines.map((m) => {
                  const badge = STATUS_BADGE[m.ftp_status] || STATUS_BADGE.FAILED;
                  const BadgeIcon = badge.icon;
                  const isUnreadable = m.ftp_status === 'FAILED' || m.ftp_status === 'PARTIAL';

                  return (
                    <tr
                      key={m.machine_no}
                      className={`hover:bg-gray/50 dark:hover:bg-meta-4/30 transition ${
                        isUnreadable ? 'bg-red-50/20 dark:bg-red-500/[0.03]' : ''
                      }`}
                    >
                      <td className="py-3 px-4 align-top">
                        <div className="font-bold text-black dark:text-white flex items-center gap-1.5">
                          <span>{m.machine_no}</span>
                          {!m.is_active && (
                            <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-gray-200 dark:bg-meta-4 text-body">
                              Non-aktif
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-body dark:text-bodydark truncate max-w-[180px]" title={m.display_name}>
                          {m.display_name}
                        </div>
                        <div className="text-[10px] text-bodydark2">{m.group_name}</div>
                      </td>

                      <td className="py-3 px-4 align-top font-mono">
                        <div className="text-black dark:text-white font-semibold">
                          {m.ip_address}:{m.ftp_port}
                        </div>
                        <div className="text-[10px] text-body dark:text-bodydark font-sans">
                          {m.controller_type}
                        </div>
                        {m.latency_ms > 0 && (
                          <div className="text-[10px] text-bodydark2">{m.latency_ms} ms</div>
                        )}
                      </td>

                      <td className="py-3 px-4 align-top">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${badge.cls}`}
                        >
                          <BadgeIcon className="h-3.5 w-3.5 shrink-0" />
                          {badge.label}
                        </span>
                        <div className="mt-1 text-[10px] font-medium text-body dark:text-bodydark">
                          {CATEGORY_LABELS[m.failure_category] || m.failure_category}
                        </div>
                        {m.active_batch && (
                          <div className="mt-0.5 text-[10px] font-mono text-body dark:text-bodydark">
                            Batch: {m.active_batch}
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-4 align-top">
                        {m.consecutive_failures > 0 ? (
                          <span className="inline-flex items-center rounded-md bg-red-100 dark:bg-red-500/15 px-2 py-0.5 text-[11px] font-bold text-red-700 dark:text-red-400">
                            {m.consecutive_failures}x siklus
                          </span>
                        ) : (
                          <span className="text-body dark:text-bodydark">-</span>
                        )}
                      </td>

                      <td className="py-3 px-4 align-top text-[11px]">
                        <div className="text-black dark:text-white">
                          Cek: {formatDateTime(m.last_checked_at)}
                        </div>
                        <div className="text-body dark:text-bodydark">
                          Sukses: {formatDateTime(m.last_success_at)}
                        </div>
                      </td>

                      <td className="py-3 px-4 align-top max-w-[340px]">
                        <p className="text-[11px] leading-relaxed text-black/80 dark:text-white/85 break-words">
                          {m.error_detail || '-'}
                        </p>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default FtpHealthMonitor;
