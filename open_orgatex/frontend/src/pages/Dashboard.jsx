import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useVisibilityInterval } from '../hooks/useVisibilityInterval';
import { 
  Server, 
  Activity, 
  CheckCircle, 
  LineChart, 
  RefreshCw, 
  Flame, 
  AlertTriangle,
  ExternalLink,
  Search,
  X,
  List,
  LayoutGrid
} from 'lucide-react';

const API_BASE = '/api';

const Dashboard = () => {
  const navigate = useNavigate();
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(new Date().toLocaleTimeString());
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'RUNNING' | 'ONLINE' | 'ALARM'
  const [viewMode, setViewMode] = useState('TABLE'); // 'TABLE' | 'GRID'

  const naturalSort = (a, b) => {
    return (a.machine_no || '').localeCompare(b.machine_no || '', undefined, { numeric: true, sensitivity: 'base' });
  };

  const fetchMachines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/machines/`);
      if (res.ok) {
        const data = await res.json();
        // Sort naturally: 1A, 1B, 2A, 2B...
        data.sort(naturalSort);

        // 1. Render immediately so the user never sees an empty dashboard
        const initial = data.map((m) => ({
          ...m,
          liveStatus: m.status || 'ONLINE',
          liveBatch: m.current_batch || '-',
          liveProgram: '-',
          liveTemp: m.current_temp ? `${m.current_temp} °C` : '-',
          liveStep: m.current_step ? `Langkah #${m.current_step}` : '-',
          hasAlarm: false,
        }));
        setMachines(initial);
        setLastRefreshed(new Date().toLocaleTimeString());

        // 2. Asynchronously enrich with live telemetry (with 2.5s timeout per request)
        const enriched = await Promise.all(
          data.map(async (m) => {
            try {
              const controller = new AbortController();
              const timeoutId = setTimeout(() => controller.abort(), 2500);
              const liveRes = await fetch(`${API_BASE}/logs/live/${m.machine_no}`, {
                signal: controller.signal
              });
              clearTimeout(timeoutId);
              if (liveRes.ok) {
                const live = await liveRes.json();
                return {
                  ...m,
                  liveStatus: live.status || m.status || 'ONLINE',
                  liveBatch: live.batch_no || m.current_batch || '-',
                  liveProgram: live.program_code ? `${live.program_code} (${live.program_name || ''})` : '-',
                  liveTemp: live.current_temp !== undefined ? `${live.current_temp} °C` : '-',
                  liveStep: live.current_step ? `Langkah #${live.current_step}` : '-',
                  hasAlarm: live.is_alarm_active || false,
                };
              }
            } catch (e) {
              // fallback
            }
            return {
              ...m,
              liveStatus: m.status || 'ONLINE',
              liveBatch: m.current_batch || '-',
              liveProgram: '-',
              liveTemp: m.current_temp ? `${m.current_temp} °C` : '-',
              liveStep: m.current_step ? `Langkah #${m.current_step}` : '-',
              hasAlarm: false,
            };
          })
        );
        enriched.sort(naturalSort);
        setMachines(enriched);
        setLastRefreshed(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Error fetching machines:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMachines();
  }, [fetchMachines]);

  // Pause polling automatically when browser tab is hidden
  useVisibilityInterval(fetchMachines, 15000, true);

  const runningCount = useMemo(() => machines.filter((m) => m.liveStatus === 'RUNNING').length, [machines]);
  const onlineCount = useMemo(() => machines.filter((m) => m.liveStatus === 'ONLINE' || m.liveStatus === 'RUNNING').length, [machines]);
  const alarmCount = useMemo(() => machines.filter((m) => m.hasAlarm).length, [machines]);

  const filteredMachines = useMemo(() => {
    return machines.filter((m) => {
      // Status filter
      if (statusFilter === 'RUNNING' && m.liveStatus !== 'RUNNING') return false;
      if (statusFilter === 'ONLINE' && m.liveStatus !== 'ONLINE' && m.liveStatus !== 'RUNNING') return false;
      if (statusFilter === 'ALARM' && !m.hasAlarm) return false;

      // Search term
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      const matchNo = (m.machine_no || '').toLowerCase().includes(term);
      const matchName = (m.display_name || '').toLowerCase().includes(term);
      const matchBatch = (m.liveBatch || '').toLowerCase().includes(term);
      const matchProg = (m.liveProgram || '').toLowerCase().includes(term);
      const matchIp = (m.ip_address || '').toLowerCase().includes(term);
      const matchStep = (m.liveStep || '').toLowerCase().includes(term);
      return matchNo || matchName || matchBatch || matchProg || matchIp || matchStep;
    });
  }, [machines, statusFilter, searchTerm]);

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold tracking-tight text-black dark:text-white">
            Process Picture
          </h2>
          <p className="text-xs text-body dark:text-bodydark mt-0.5">
            Monitoring status operasional dan telemetri mesin celup tekstil secara realtime
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-body dark:text-bodydark font-mono tabular-nums">
            {lastRefreshed}
          </span>
          <button
            onClick={fetchMachines}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm transition-colors cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* STATS OVERVIEW CARDS (INTERACTIVE ACCESSIBLE BUTTON FILTERS) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <button
          type="button"
          onClick={() => setStatusFilter('ALL')}
          aria-pressed={statusFilter === 'ALL'}
          className={`text-left rounded-xl border p-4.5 shadow-sm transition-all cursor-pointer ${
            statusFilter === 'ALL'
              ? 'border-primary ring-2 ring-primary/20 bg-primary/5 dark:bg-primary/10'
              : 'border-stroke bg-white hover:border-primary/50 dark:border-strokedark dark:bg-boxdark'
          }`}
          title="Klik untuk tampilkan semua mesin"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Total Mesin
            </span>
            <div className="p-2 rounded-lg bg-primary/10 text-primary dark:bg-primary/20 dark:text-secondary">
              <Server className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-black dark:text-bodydark1 font-mono tabular-nums">
            {machines.length} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter(statusFilter === 'RUNNING' ? 'ALL' : 'RUNNING')}
          aria-pressed={statusFilter === 'RUNNING'}
          className={`text-left rounded-xl border p-4.5 shadow-sm transition-all cursor-pointer ${
            statusFilter === 'RUNNING'
              ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-500/10'
              : 'border-stroke bg-white hover:border-emerald-500/50 dark:border-strokedark dark:bg-boxdark'
          }`}
          title="Klik untuk filter mesin yang sedang jalan"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Sedang Jalan
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-emerald-600 dark:text-emerald-400 font-mono tabular-nums">
            {runningCount} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter(statusFilter === 'ONLINE' ? 'ALL' : 'ONLINE')}
          aria-pressed={statusFilter === 'ONLINE'}
          className={`text-left rounded-xl border p-4.5 shadow-sm transition-all cursor-pointer ${
            statusFilter === 'ONLINE'
              ? 'border-sky-500 ring-2 ring-sky-500/20 bg-sky-500/10'
              : 'border-stroke bg-white hover:border-sky-500/50 dark:border-strokedark dark:bg-boxdark'
          }`}
          title="Klik untuk filter mesin online"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Online
            </span>
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <CheckCircle className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-black dark:text-white font-mono tabular-nums">
            {onlineCount} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
        </button>

        <button
          type="button"
          onClick={() => setStatusFilter(statusFilter === 'ALARM' ? 'ALL' : 'ALARM')}
          aria-pressed={statusFilter === 'ALARM'}
          className={`text-left rounded-xl border p-4.5 shadow-sm transition-all cursor-pointer ${
            statusFilter === 'ALARM'
              ? 'border-rose-500 ring-2 ring-rose-500/20 bg-rose-500/10'
              : 'border-stroke bg-white hover:border-rose-500/50 dark:border-strokedark dark:bg-boxdark'
          }`}
          title="Klik untuk filter mesin yang mengalami alarm"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Alarm
            </span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-rose-600 dark:text-rose-400 font-mono tabular-nums">
            {alarmCount} <span className="text-xs font-semibold text-body">Mesin</span>
          </h4>
        </button>
      </div>

      {/* MAIN CONTAINER: DAFTAR MESIN */}
      <div className="rounded-xl border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark overflow-hidden">
        {/* TOOLBAR */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3.5 p-4 md:px-6 border-b border-stroke dark:border-strokedark bg-white dark:bg-boxdark">
          <div className="flex items-center gap-3">
            <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
              Daftar Mesin
            </h4>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-primary/10 text-primary dark:text-secondary font-bold">
              {filteredMachines.length} Mesin
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* SEARCH INPUT */}
            <div className="relative min-w-[200px] sm:min-w-[280px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Cari mesin, batch, program, IP..."
                className="w-full pl-9 pr-8 py-1.5 text-xs bg-gray dark:bg-meta-4/60 border border-stroke dark:border-strokedark rounded-lg outline-none focus:border-primary text-black dark:text-white transition-colors"
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-black dark:hover:text-white"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* STATUS FILTER PILLS */}
            <div className="flex items-center gap-1 bg-gray dark:bg-meta-4/50 p-1 rounded-lg border border-stroke dark:border-strokedark text-xs">
              <button
                onClick={() => setStatusFilter('ALL')}
                className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                  statusFilter === 'ALL'
                    ? 'bg-white dark:bg-boxdark text-black dark:text-white shadow-2xs'
                    : 'text-body dark:text-bodydark hover:text-black dark:hover:text-white'
                }`}
              >
                Semua
              </button>
              <button
                onClick={() => setStatusFilter('RUNNING')}
                className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                  statusFilter === 'RUNNING'
                    ? 'bg-emerald-500 text-white shadow-2xs'
                    : 'text-body dark:text-bodydark hover:text-emerald-600'
                }`}
              >
                Jalan ({runningCount})
              </button>
              <button
                onClick={() => setStatusFilter('ALARM')}
                className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                  statusFilter === 'ALARM'
                    ? 'bg-rose-500 text-white shadow-2xs'
                    : 'text-body dark:text-bodydark hover:text-rose-600'
                }`}
              >
                Alarm ({alarmCount})
              </button>
            </div>

            {/* VIEW MODE TOGGLE (TABLE LIST vs CARD GRID) */}
            <div className="flex items-center gap-1 bg-gray dark:bg-meta-4/50 p-1 rounded-lg border border-stroke dark:border-strokedark">
              <button
                onClick={() => setViewMode('TABLE')}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === 'TABLE'
                    ? 'bg-white dark:bg-boxdark text-primary dark:text-secondary shadow-2xs font-bold'
                    : 'text-body dark:text-bodydark hover:text-black dark:hover:text-white'
                }`}
                title="Tampilan Tabel List"
              >
                <List className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('GRID')}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === 'GRID'
                    ? 'bg-white dark:bg-boxdark text-primary dark:text-secondary shadow-2xs font-bold'
                    : 'text-body dark:text-bodydark hover:text-black dark:hover:text-white'
                }`}
                title="Tampilan Grid Card"
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* SKELETON LOADING STATE (INITIAL LOAD) */}
        {loading && machines.length === 0 && (
          <div className="p-6 space-y-3 animate-pulse" role="status" aria-label="Memuat daftar mesin">
            {[1, 2, 3, 4, 5].map((row) => (
              <div key={row} className="h-12 rounded-lg bg-gray-100 dark:bg-meta-4/40" />
            ))}
          </div>
        )}

        {/* EMPTY STATE */}
        {filteredMachines.length === 0 && !loading && (
          <div className="py-16 text-center text-body dark:text-bodydark">
            <Server className="h-10 w-10 mx-auto text-body/40 mb-3 animate-pulse" />
            <p className="font-semibold text-sm text-black dark:text-white">Tidak ada mesin yang sesuai kriteria pencarian.</p>
            <p className="text-xs text-body mt-1">Coba ubah kata kunci pencarian atau reset filter status.</p>
            <button
              onClick={() => { setSearchTerm(''); setStatusFilter('ALL'); }}
              className="mt-4 px-4 py-1.5 text-xs bg-primary text-white rounded-lg hover:bg-primary/90 font-medium transition-colors"
            >
              Reset Filter
            </button>
          </div>
        )}

        {/* 1. TABLE LIST VIEW (DEFAULT & COMPACT INDUSTRIAL VIEW) */}
        {viewMode === 'TABLE' && filteredMachines.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50/80 dark:bg-meta-4/30 border-b border-stroke dark:border-strokedark text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
                  <th className="py-3 px-4 text-center w-12">#</th>
                  <th className="py-3 px-4">Mesin</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Batch Aktif</th>
                  <th className="py-3 px-4">Program Resep</th>
                  <th className="py-3 px-4">Langkah Celup</th>
                  <th className="py-3 px-4">Suhu Bejana (PV)</th>
                  <th className="py-3 px-4">IP Controller HMI</th>
                  <th className="py-3 px-4 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stroke dark:divide-strokedark text-xs">
                {filteredMachines.map((m, idx) => {
                  const isRunning = m.liveStatus === 'RUNNING';
                  return (
                    <tr
                      key={m.machine_no}
                      className={`hover:bg-primary/5 dark:hover:bg-meta-4/40 transition-colors ${
                        isRunning ? 'bg-emerald-50/15 dark:bg-meta-4/10' : ''
                      }`}
                    >
                      {/* INDEX */}
                      <td className="py-3.5 px-4 text-center font-mono text-gray-400">
                        {idx + 1}
                      </td>

                      {/* MESIN */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2.5">
                          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                            isRunning 
                              ? 'bg-emerald-500 animate-pulse' 
                              : 'bg-slate-300 dark:bg-slate-600'
                          }`} />
                          <div>
                            <span className="font-extrabold text-sm text-black dark:text-white tracking-wide">
                              Mesin {m.machine_no}
                            </span>
                            <span className="block text-[11px] text-body dark:text-bodydark font-mono">
                              {m.display_name && m.display_name !== m.machine_no ? m.display_name : (m.controller_type || 'Controller')}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* STATUS */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                            isRunning
                              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                              : m.liveStatus === 'ONLINE'
                                ? 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/30'
                                : 'bg-gray dark:bg-meta-4 text-body dark:text-bodydark border border-stroke/40 dark:border-strokedark'
                          }`}>
                            {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                            {m.liveStatus}
                          </span>
                          {m.hasAlarm && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500 text-white animate-pulse">
                              <AlertTriangle className="h-3 w-3" />
                              ALARM
                            </span>
                          )}
                        </div>
                      </td>

                      {/* BATCH AKTIF */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono font-bold text-xs text-black dark:text-white bg-gray dark:bg-meta-4/60 px-2 py-1 rounded border border-stroke/50 dark:border-strokedark">
                          {m.liveBatch}
                        </span>
                      </td>

                      {/* PROGRAM RESEP */}
                      <td className="py-3.5 px-4">
                        <span className="font-medium text-black dark:text-white block max-w-xs truncate" title={m.liveProgram}>
                          {m.liveProgram}
                        </span>
                      </td>

                      {/* LANGKAH CELUP */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono font-bold text-primary dark:text-secondary">
                          {m.liveStep}
                        </span>
                      </td>

                      {/* SUHU BEJANA (PV) */}
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1 font-bold font-mono text-rose-600 dark:text-rose-400 text-sm">
                          <Flame className="h-4 w-4 shrink-0 text-rose-500" />
                          {m.liveTemp}
                        </span>
                      </td>

                      {/* IP CONTROLLER HMI */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono text-xs text-body dark:text-bodydark">
                          {m.ip_address}
                        </span>
                      </td>

                      {/* AKSI */}
                      <td className="py-3.5 px-4 text-center">
                        <button
                          onClick={() => navigate(`/process-analyser?machine=${m.machine_no}`)}
                          className="inline-flex items-center gap-1.5 py-1.5 px-3 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded-lg shadow-2xs hover:shadow transition-all whitespace-nowrap cursor-pointer"
                        >
                          <LineChart className="h-3.5 w-3.5" />
                          Grafik Kurva
                          <ExternalLink className="h-3 w-3 opacity-70" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* 2. GRID CARD VIEW (ALTERNATIVE) */}
        {viewMode === 'GRID' && filteredMachines.length > 0 && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredMachines.map((m) => {
              const isRunning = m.liveStatus === 'RUNNING';
              return (
                <div 
                  key={m.machine_no}
                  className={`rounded-xl border transition-all duration-200 overflow-hidden shadow-sm ${
                    isRunning 
                      ? 'border-primary/50 bg-gradient-to-b from-blue-50/40 to-white dark:from-meta-4/30 dark:to-boxdark' 
                      : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:border-stroke/80'
                  }`}
                >
                  {/* Tile Header */}
                  <div className="flex items-center justify-between px-5 py-3.5 border-b border-stroke/60 dark:border-strokedark">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                      <span className="font-extrabold text-base text-black dark:text-white tracking-wide">
                        Mesin {m.machine_no}
                      </span>
                      <span className="text-xs text-body dark:text-bodydark font-mono">({m.display_name || m.machine_no})</span>
                    </div>
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                      isRunning 
                        ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30' 
                        : 'bg-gray dark:bg-meta-4 text-body dark:text-bodydark border border-stroke/40 dark:border-strokedark'
                    }`}>
                      {m.liveStatus}
                    </span>
                  </div>

                  {/* Tile Body: Key Production Metrics */}
                  <div className="p-5 space-y-3.5">
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-gray dark:bg-meta-4/60 p-3 rounded-lg border border-stroke/40 dark:border-strokedark">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-body dark:text-bodydark2 block">Batch Aktif:</span>
                        <span className="font-bold text-sm text-black dark:text-white font-mono tabular-nums truncate block mt-0.5">
                          {m.liveBatch}
                        </span>
                      </div>
                      <div className="bg-gray dark:bg-meta-4/60 p-3 rounded-lg border border-stroke/40 dark:border-strokedark">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-body dark:text-bodydark2 block">Suhu Aktual (PV):</span>
                        <span className="font-bold text-sm text-rose-600 dark:text-rose-400 font-mono tabular-nums flex items-center gap-1 mt-0.5">
                          <Flame className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
                          {m.liveTemp}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2 text-xs text-body dark:text-bodydark">
                      <div className="flex justify-between items-center">
                        <span className="text-body dark:text-bodydark font-medium">Program Resep:</span>
                        <span className="font-bold text-black dark:text-white truncate max-w-[180px]">
                          {m.liveProgram}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-body dark:text-bodydark font-medium">Langkah Celup:</span>
                        <span className="font-bold text-primary dark:text-secondary font-mono">{m.liveStep}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-body dark:text-bodydark font-medium">IP Controller HMI:</span>
                        <span className="font-mono text-black dark:text-white font-medium">{m.ip_address}</span>
                      </div>
                    </div>

                    {/* ACTION: BUKA PROCESS ANALYSER */}
                    <div className="pt-2">
                      <button
                        onClick={() => navigate(`/process-analyser?machine=${m.machine_no}`)}
                        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-primary hover:bg-primary/90 dark:bg-primary dark:hover:bg-primary/90 rounded-lg shadow-sm transition-all cursor-pointer"
                      >
                        <LineChart className="h-4 w-4" />
                        Buka Process Analyser (Grafik Kurva)
                        <ExternalLink className="h-3.5 w-3.5 opacity-70" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
