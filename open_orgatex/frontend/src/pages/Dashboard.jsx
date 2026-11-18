import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Server, 
  Activity, 
  CheckCircle, 
  Clock, 
  LineChart, 
  RefreshCw, 
  Flame, 
  AlertTriangle,
  Play,
  Layers,
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
          <div className="flex items-center gap-2">
            <h2 className="text-xl md:text-2xl font-bold text-black dark:text-white">
              Process Picture (Online Machine Mimic)
            </h2>
            <span className="text-xs bg-primary/10 text-primary font-bold px-2 py-0.5 rounded border border-primary/20">
              OLN420 Parity
            </span>
          </div>
          <p className="text-xs text-body dark:text-gray-400 mt-1">
            Monitoring terpusat status visual mesin pencelupan SETEX Secom 777 & jalan pintas ke Process Analyser.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">Update terakhir: {lastRefreshed}</span>
          <button
            onClick={fetchMachines}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* STATS OVERVIEW */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded border border-stroke bg-white p-4 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-body dark:text-gray-400">Total Mesin Terhubung</span>
            <Server className="h-4 w-4 text-primary" />
          </div>
          <h4 className="mt-2 text-xl font-bold text-black dark:text-white">{machines.length} Unit</h4>
          <span className="text-[11px] text-success font-medium">Semua unit terdaftar di Postgres</span>
        </div>

        <div className="rounded border border-stroke bg-white p-4 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-body dark:text-gray-400">Batch Sedang Berjalan</span>
            <Activity className="h-4 w-4 text-meta-3" />
          </div>
          <h4 className="mt-2 text-xl font-bold text-meta-3">{runningCount} Unit</h4>
          <span className="text-[11px] text-body dark:text-gray-400">Proses pencelupan aktif</span>
        </div>

        <div className="rounded border border-stroke bg-white p-4 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-body dark:text-gray-400">Mesin Online</span>
            <CheckCircle className="h-4 w-4 text-success" />
          </div>
          <h4 className="mt-2 text-xl font-bold text-success">{onlineCount} Unit</h4>
          <span className="text-[11px] text-body dark:text-gray-400">Komunikasi HMI/FTP aktif</span>
        </div>

        <div className="rounded border border-stroke bg-white p-4 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-body dark:text-gray-400">Alarm / Intervensi</span>
            <AlertTriangle className="h-4 w-4 text-danger" />
          </div>
          <h4 className="mt-2 text-xl font-bold text-danger">{alarmCount} Mesin</h4>
          <span className="text-[11px] text-danger font-medium">Memerlukan perhatian operator</span>
        </div>
      </div>

      {/* MACHINE TILES GRID */}
      <div className="rounded border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark">
        <div className="flex items-center justify-between py-3.5 px-6 border-b border-stroke dark:border-strokedark">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
              Daftar Mesin & Mimic Visual Real-Time
            </h4>
            <span className="text-xs text-gray-500">
              (Klik "Buka Process Analyser" pada mesin untuk membaca grafik kurva & telemetri)
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {machines.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-gray-500">
              <Server className="h-10 w-10 mx-auto text-gray-400 mb-2 animate-pulse" />
              <p className="font-semibold text-sm text-black dark:text-white">Tidak ada data mesin ditemukan.</p>
              <p className="text-xs text-gray-400 mt-1">Tekan tombol 'Refresh' atau periksa koneksi database PostgreSQL / SQLite.</p>
              <button
                onClick={fetchMachines}
                className="mt-3 px-4 py-1.5 text-xs bg-primary text-white rounded hover:bg-primary/90 font-medium"
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
                className={`rounded-lg border transition-all duration-200 overflow-hidden shadow-sm ${
                  isRunning 
                    ? 'border-primary/40 bg-gradient-to-b from-blue-50/30 to-white dark:from-meta-4/20 dark:to-boxdark-2' 
                    : 'border-stroke dark:border-strokedark bg-white dark:bg-boxdark-2'
                }`}
              >
                {/* Tile Header */}
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-stroke/60 dark:border-strokedark">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-3 h-3 rounded-full ${isRunning ? 'bg-meta-3 animate-ping' : 'bg-gray-400'}`} />
                    <span className="font-extrabold text-base text-black dark:text-white tracking-wide">
                      Mesin {m.machine_no}
                    </span>
                    <span className="text-xs text-gray-500 font-mono">({m.display_name || m.machine_no})</span>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                    isRunning 
                      ? 'bg-meta-3 text-white shadow-sm' 
                      : 'bg-gray-200 dark:bg-meta-4 text-gray-700 dark:text-gray-300'
                  }`}>
                    {m.liveStatus}
                  </span>
                </div>

                {/* Tile Body: Key Production Metrics */}
                <div className="p-5 space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-gray-50 dark:bg-meta-4/40 p-2.5 rounded border border-gray-100 dark:border-strokedark">
                      <span className="text-[10px] text-gray-500 block">Batch Aktif:</span>
                      <span className="font-bold text-sm text-black dark:text-white font-mono">
                        {m.liveBatch}
                      </span>
                    </div>
                    <div className="bg-gray-50 dark:bg-meta-4/40 p-2.5 rounded border border-gray-100 dark:border-strokedark">
                      <span className="text-[10px] text-gray-500 block">Suhu Aktual (PV):</span>
                      <span className="font-bold text-sm text-danger font-mono flex items-center gap-1">
                        <Flame className="h-3.5 w-3.5 text-danger" />
                        {m.liveTemp}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-xs text-gray-600 dark:text-gray-300">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Program Resep:</span>
                      <span className="font-semibold text-black dark:text-white truncate max-w-[180px]">
                        {m.liveProgram}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Langkah Celup:</span>
                      <span className="font-semibold text-primary">{m.liveStep}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">IP Controller HMI:</span>
                      <span className="font-mono text-gray-700 dark:text-gray-300">{m.ip_address}</span>
                    </div>
                  </div>

                  {/* ACTION: BUKA PROCESS ANALYSER (GRAFIK KURVA) */}
                  <div className="pt-2">
                    <button
                      onClick={() => navigate(`/process-analyser?machine=${m.machine_no}`)}
                      className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded shadow-sm transition-colors"
                    >
                      <LineChart className="h-4 w-4" />
                      Buka Process Analyser (Grafik Kurva)
                      <ExternalLink className="h-3 w-3 opacity-70" />
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
