import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Server, 
  Activity, 
  CheckCircle, 
  LineChart, 
  RefreshCw, 
  Flame, 
  AlertTriangle,
  ExternalLink
} from 'lucide-react';

const API_BASE = '/api';

const Dashboard = () => {
  const navigate = useNavigate();
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(new Date().toLocaleTimeString());

  const fetchMachines = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/machines/`);
      if (res.ok) {
        const data = await res.json();
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
        setMachines(enriched);
        setLastRefreshed(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Error fetching machines:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMachines();
    const interval = setInterval(fetchMachines, 15000); // 15s refresh
    return () => clearInterval(interval);
  }, []);

  const runningCount = machines.filter((m) => m.liveStatus === 'RUNNING').length;
  const onlineCount = machines.filter((m) => m.liveStatus === 'ONLINE' || m.liveStatus === 'RUNNING').length;
  const alarmCount = machines.filter((m) => m.hasAlarm).length;

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl md:text-2xl font-extrabold tracking-tight text-black dark:text-white">
              Process Picture (Online Machine Mimic)
            </h2>
            <span className="text-[11px] bg-primary/10 text-primary dark:bg-primary/20 dark:text-secondary font-bold px-2 py-0.5 rounded-md border border-primary/20 uppercase tracking-wider">
              OLN420 Parity
            </span>
          </div>
          <p className="text-xs text-body dark:text-bodydark mt-1 font-medium">
            Monitoring terpusat status visual mesin pencelupan SETEX Secom 777 & jalan pintas ke Process Analyser.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-body dark:text-bodydark font-mono tabular-nums">
            Update terakhir: {lastRefreshed}
          </span>
          <button
            onClick={fetchMachines}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* STATS OVERVIEW CARDS (TAILADMIN SMM STYLE) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-stroke bg-white p-4.5 shadow-sm dark:border-strokedark dark:bg-boxdark hover:border-primary/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Total Mesin Terhubung
            </span>
            <div className="p-2 rounded-lg bg-primary/10 text-primary dark:bg-primary/20 dark:text-secondary">
              <Server className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-black dark:text-bodydark1 font-mono tabular-nums">
            {machines.length} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
          <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold mt-1 block">
            Semua unit terdaftar di Postgres
          </span>
        </div>

        <div className="rounded-xl border border-stroke bg-white p-4.5 shadow-sm dark:border-strokedark dark:bg-boxdark hover:border-emerald-500/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Batch Sedang Berjalan
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-emerald-600 dark:text-emerald-400 font-mono tabular-nums">
            {runningCount} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
          <span className="text-[11px] text-body dark:text-bodydark font-medium mt-1 block">
            Proses pencelupan aktif
          </span>
        </div>

        <div className="rounded-xl border border-stroke bg-white p-4.5 shadow-sm dark:border-strokedark dark:bg-boxdark hover:border-sky-500/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Mesin Online
            </span>
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <CheckCircle className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-black dark:text-white font-mono tabular-nums">
            {onlineCount} <span className="text-xs font-semibold text-body">Unit</span>
          </h4>
          <span className="text-[11px] text-body dark:text-bodydark font-medium mt-1 block">
            Komunikasi HMI/FTP aktif
          </span>
        </div>

        <div className="rounded-xl border border-stroke bg-white p-4.5 shadow-sm dark:border-strokedark dark:bg-boxdark hover:border-rose-500/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
              Alarm / Intervensi
            </span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <h4 className="mt-2 text-2xl font-extrabold tracking-tight text-rose-600 dark:text-rose-400 font-mono tabular-nums">
            {alarmCount} <span className="text-xs font-semibold text-body">Mesin</span>
          </h4>
          <span className="text-[11px] text-rose-600 dark:text-rose-400 font-semibold mt-1 block">
            Memerlukan perhatian operator
          </span>
        </div>
      </div>

      {/* MACHINE TILES GRID */}
      <div className="rounded-xl border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark overflow-hidden">
        <div className="flex items-center justify-between py-3.5 px-6 border-b border-stroke dark:border-strokedark">
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider">
              Daftar Mesin & Mimic Visual Real-Time
            </h4>
            <span className="text-xs text-body dark:text-bodydark font-medium hidden sm:inline">
              (Klik "Buka Process Analyser" pada mesin untuk membaca grafik kurva & telemetri)
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {machines.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-body dark:text-bodydark">
              <Server className="h-10 w-10 mx-auto text-body/50 mb-2 animate-pulse" />
              <p className="font-semibold text-sm text-black dark:text-white">Tidak ada data mesin ditemukan.</p>
              <p className="text-xs text-body mt-1">Tekan tombol 'Refresh' atau periksa koneksi database PostgreSQL / SQLite.</p>
              <button
                onClick={fetchMachines}
                className="mt-3 px-4 py-1.5 text-xs bg-primary text-white rounded-lg hover:bg-primary/90 font-medium transition-colors"
              >
                Muat Ulang Mesin
              </button>
            </div>
          )}
          {machines.map((m) => {
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
                      className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-primary hover:bg-primary/90 dark:bg-primary dark:hover:bg-primary/90 rounded-lg shadow-sm transition-all"
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
      </div>
    </div>
  );
};

export default Dashboard;
