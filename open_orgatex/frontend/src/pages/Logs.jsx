import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import TempCurveChart from '../components/Charts/TempCurveChart';
import { 
  LineChart, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Database, 
  Flame, 
  Play, 
  Clock, 
  ShieldAlert, 
  Server,
  Layers,
  ChevronRight,
  Sliders,
  Gauge,
  Activity,
  Wifi,
  Calendar,
  Filter,
  UserCheck,
  CalendarDays,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown
} from 'lucide-react';

const API_BASE = '/api';

const Logs = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = new URLSearchParams(location.search);
  const initialMachineFromUrl = searchParams.get('machine');

  const [selectedMachine, setSelectedMachine] = useState(initialMachineFromUrl || '1A');
  const [machines, setMachines] = useState(['1A']);
  const [rawMachines, setRawMachines] = useState([]);
  const [hmiIp, setHmiIp] = useState('172.16.110.101');
  const [refreshInterval, setRefreshInterval] = useState(3000); // 3 detik default realtime
  const [activeTab, setActiveTab] = useState('active'); // 'active' or 'archive'
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [liveData, setLiveData] = useState(null);
  const [chartSeries, setChartSeries] = useState([]);
  const [chartCategories, setChartCategories] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [lastUpdated, setLastUpdated] = useState('');

  // Filter Alarms & Intervensi HMI berdasarkan tanggal & Order By Date Time
  const [selectedAlarmDate, setSelectedAlarmDate] = useState('');
  const [alarmFilterCategory, setAlarmFilterCategory] = useState('ALL');
  const [alarmSortOrder, setAlarmSortOrder] = useState('desc'); // 'desc' (terbaru ke terlama) atau 'asc' (terlama ke terbaru)
  const [availableAlarmDates, setAvailableAlarmDates] = useState([]);
  const [alarmsLoading, setAlarmsLoading] = useState(false);

  // Fetch real machines from PostgreSQL
  useEffect(() => {
    fetch(`${API_BASE}/machines/`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setRawMachines(data);
          const list = data.map((m) => m.machine_no);
          setMachines(list);
          const currentUrlParam = new URLSearchParams(window.location.search).get('machine');
          const targetMach = currentUrlParam && list.includes(currentUrlParam) ? currentUrlParam : (list.includes(selectedMachine) ? selectedMachine : list[0]);
          setSelectedMachine(targetMach);
          const matched = data.find((m) => m.machine_no === targetMach);
          if (matched && matched.ip_address) {
            setHmiIp(matched.ip_address);
          }
        }
      })
      .catch((err) => console.error('Gagal mengambil daftar mesin:', err));
  }, [location.search]);

  // Fetch Live Data on-the-fly from the controller & Postgres
  const fetchLiveLog = async (isManual = false) => {
    if (!selectedMachine) return;
    if (isManual || !liveData) {
      setLoading(true);
    }
    try {
      const q = hmiIp ? `?ip=${encodeURIComponent(hmiIp)}` : '';
      const res = await fetch(`${API_BASE}/logs/live/${selectedMachine}${q}`);
      if (res.ok) {
        const data = await res.json();
        setLiveData(data);
        if (data.hmi_ip && data.hmi_ip !== hmiIp && !hmiIp) {
          setHmiIp(data.hmi_ip);
        }
        setLastUpdated(new Date().toLocaleTimeString());

        // Format chart series
        if (data.curve && data.curve.length > 0) {
          const cats = data.curve.map((pt) => {
            const parts = pt.timestamp.split(' ');
            return parts[1] || pt.timestamp;
          });
          const pv = data.curve.map((pt) => pt.temp_pv);
          const sp = data.curve.map((pt) => pt.temp_sp);
          const t2 = data.curve.map((pt) => pt.temp_pt100_t2);

          setChartCategories(cats);
          setChartSeries([
            { name: 'Suhu Aktual Bejana (PV °C)', data: pv },
            { name: 'Setpoint Suhu (SP °C)', data: sp },
            { name: 'Sensor PT100 Tambahan (T2 °C)', data: t2 },
          ]);
        }

        // Set alarms only if user is not currently viewing a specific filtered date
        if (!selectedAlarmDate && alarmFilterCategory === 'ALL') {
          if (Array.isArray(data.alarms) && data.alarms.length > 0) {
            setAlarms(data.alarms);
          } else if (Array.isArray(data.active_alarms) && data.active_alarms.length > 0) {
            setAlarms(data.active_alarms);
          }
        }
      }
    } catch (err) {
      console.error('Gagal mengambil data live:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch Alarms & Intervensi HMI berdasarkan tanggal & Order By Date Time
  const fetchAlarms = async (
    mach = selectedMachine, 
    dateFilter = selectedAlarmDate, 
    cat = alarmFilterCategory, 
    sortOrd = alarmSortOrder
  ) => {
    if (!mach) return;
    setAlarmsLoading(true);
    try {
      const q = new URLSearchParams();
      if (dateFilter) q.append('date', dateFilter);
      if (cat && cat !== 'ALL') q.append('category', cat);
      q.append('order_by', 'datetime');
      q.append('order', sortOrd);
      const res = await fetch(`${API_BASE}/logs/alarms/${mach}?${q.toString()}`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.alarms)) {
          setAlarms(data.alarms);
        }
        if (Array.isArray(data.available_dates)) {
          setAvailableAlarmDates(data.available_dates);
        }
      }
    } catch (err) {
      console.error('Gagal mengambil data alarm berdasarkan tanggal & order by datetime:', err);
    } finally {
      setAlarmsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlarms(selectedMachine, selectedAlarmDate, alarmFilterCategory, alarmSortOrder);
  }, [selectedMachine, selectedAlarmDate, alarmFilterCategory, alarmSortOrder]);

  useEffect(() => {
    fetchLiveLog();
    if (refreshInterval > 0) {
      const interval = setInterval(fetchLiveLog, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [selectedMachine, hmiIp, refreshInterval]);

  // Trigger manual sync
  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/logs/sync/${selectedMachine}`, { method: 'POST' });
      if (res.ok) {
        const syncRes = await res.json();
        alert(
          `Sinkronisasi Selesai!\n- Titik telemetri baru tersimpan: ${syncRes.new_points_persisted}\n- Alarm baru: ${syncRes.new_alarms_persisted}\n- Database: PostgreSQL TimescaleDB`
        );
        fetchLiveLog();
        fetchAlarms();
      }
    } catch (err) {
      alert(`Gagal sinkronisasi: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const FUNCTION_MAP = {
    1: { name: 'Start Program', type: 'START', icon: '1' },
    2: { name: 'End Program', type: 'END', icon: '2' },
    713: { name: 'Fill / Isi Air', type: 'FILL', icon: '713' },
    85: { name: 'Dosing Bahan Kimia', type: 'DOSE', icon: '85' },
    86: { name: 'Dosing Bahan Kimia', type: 'DOSE', icon: '86' },
    141: { name: 'Heating / Pemanasan', type: 'HEAT', icon: '141' },
    121: { name: 'Holding / Penahanan Suhu', type: 'HOLD', icon: '121' },
    131: { name: 'Cooling / Pendinginan', type: 'COOL', icon: '131' },
    61: { name: 'Drain / Buang Larutan', type: 'DRAIN', icon: '61' },
    71: { name: 'Drain / Buang Larutan', type: 'DRAIN', icon: '71' },
    714: { name: 'Washing / Bilas', type: 'WASH', icon: '714' },
    106: { name: 'Call-Off Operator', type: 'OP', icon: '106' },
  };

  const defaultCycleSteps = [
    { no: 1, name: 'Fill / Isi Air', type: 'FILL', icon: '713' },
    { no: 2, name: 'Dosing Bahan Kimia', type: 'DOSE', icon: '85' },
    { no: 3, name: 'Heating / Pemanasan', type: 'HEAT', icon: '141' },
    { no: 4, name: 'Holding / Penahanan Suhu', type: 'HOLD', icon: '121' },
    { no: 5, name: 'Cooling / Pendinginan', type: 'COOL', icon: '131' },
    { no: 6, name: 'Drain / Buang Larutan', type: 'DRAIN', icon: '61' },
    { no: 7, name: 'Washing / Bilas', type: 'WASH', icon: '714' },
    { no: 8, name: 'Holding / Penahanan Suhu', type: 'HOLD', icon: '121' },
    { no: 9, name: 'Cooling / Pendinginan', type: 'COOL', icon: '131' },
    { no: 10, name: 'Drain / Buang Larutan', type: 'DRAIN', icon: '61' },
  ];

  const currentStepNo = liveData?.current_step || 1;
  const totalDisplaySteps = Math.max(7, currentStepNo);
  const stepsList = Array.from({ length: totalDisplaySteps }, (_, i) => {
    const sNo = i + 1;
    if (sNo === currentStepNo && liveData?.function_code && FUNCTION_MAP[liveData.function_code]) {
      return { no: sNo, ...FUNCTION_MAP[liveData.function_code] };
    }
    const def = defaultCycleSteps.find(s => s.no === sNo);
    if (def) return def;
    return { no: sNo, name: `Langkah #${sNo}`, type: 'PROCESS', icon: '121' };
  });

  return (
    <div className="space-y-6">
      {/* HEADER & ORGATEX TOOLBAR */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl md:text-2xl font-bold text-black dark:text-white">
              Process Analyser (Grafik Kurva Telemetri)
            </h2>
            <span className="text-xs bg-primary/10 text-primary font-bold px-2 py-0.5 rounded border border-primary/20">
              FEN240 Parity
            </span>
            <span className="text-xs bg-success/10 text-success font-bold px-2 py-0.5 rounded border border-success/20">
              Live TimescaleDB
            </span>
            {liveData?.is_live_hmi ? (
              <span className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/30 flex items-center gap-1.5" title={`Terhubung ke ${liveData.data_source}`}>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Live HMI ({liveData?.hmi_ip || hmiIp})
              </span>
            ) : (
              <span className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold px-2 py-0.5 rounded border border-amber-500/30 flex items-center gap-1.5" title={`Mode: ${liveData?.data_source || 'Storage Lokal'}`}>
                <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                Target: {hmiIp || '172.16.110.101'} (Offline/Fallback)
              </span>
            )}
          </div>
          <p className="text-xs text-body dark:text-gray-400 mt-1">
            Visualisasi kurva telemetri langsung dari HMI SETEX Secom 777 (<code className="text-primary font-mono font-bold">ftp://{hmiIp || '172.16.110.101'}/Storage/SC777CE/STATUS/STATUS.ACT</code>)
          </p>
        </div>

        {/* CONTROLS */}
        <div className="flex flex-wrap items-center gap-3">
          {/* IP HMI INPUT */}
          <div className="flex items-center gap-1.5 bg-white dark:bg-boxdark px-2.5 py-1.5 rounded border border-stroke dark:border-strokedark shadow-sm">
            <Wifi className={`h-3.5 w-3.5 ${liveData?.is_live_hmi ? 'text-emerald-500' : 'text-gray-400'}`} />
            <span className="text-[11px] font-semibold text-gray-700 dark:text-gray-300">IP HMI:</span>
            <input
              type="text"
              value={hmiIp}
              onChange={(e) => setHmiIp(e.target.value)}
              placeholder="172.16.110.101"
              className="text-xs font-mono font-bold text-black dark:text-white bg-transparent outline-none w-28"
              title="IP Address Controller SETEX 777CE (Port FTP 21)"
            />
          </div>

          {/* REFRESH INTERVAL DROPDOWN */}
          <div className="flex items-center gap-1.5 bg-white dark:bg-boxdark px-2.5 py-1.5 rounded border border-stroke dark:border-strokedark shadow-sm">
            <Clock className="h-3.5 w-3.5 text-primary" />
            <span className="text-[11px] font-semibold text-gray-500">Auto Refresh:</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="text-xs font-bold text-black dark:text-white bg-transparent outline-none cursor-pointer"
            >
              <option value={2000}>2 Detik (Realtime Cepat)</option>
              <option value={3000}>3 Detik (Realtime)</option>
              <option value={5000}>5 Detik</option>
              <option value={15000}>15 Detik</option>
              <option value={60000}>1 Menit</option>
              <option value={0}>Pause</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-white dark:bg-boxdark px-3 py-1.5 rounded border border-stroke dark:border-strokedark shadow-sm">
            <Server className="h-4 w-4 text-primary" />
            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Pilih Mesin:</span>
            <select
              value={selectedMachine}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedMachine(val);
                navigate(`/process-analyser?machine=${val}`);
                const matched = rawMachines.find((m) => m.machine_no === val);
                if (matched && matched.ip_address) {
                  setHmiIp(matched.ip_address);
                }
              }}
              className="text-xs font-bold text-black dark:text-white bg-transparent outline-none cursor-pointer"
            >
              {machines.map((m) => (
                <option key={m} value={m} className="dark:bg-boxdark">
                  Mesin {m}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchLiveLog(true)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <button
            onClick={handleSyncNow}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded shadow-sm transition-colors"
          >
            <Database className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Menyimpan ke DB...' : 'Sinkron ke Postgres'}
          </button>
        </div>
      </div>

      {/* TABS: ACTIVE BATCH VS ARCHIVE (ORGATEX WORKPLACE PARITY) */}
      <div className="flex border-b border-stroke dark:border-strokedark">
        <button
          onClick={() => setActiveTab('active')}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors ${
            activeTab === 'active'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
          }`}
        >
          <Activity className="h-4 w-4" />
          Active Batch (Live Kurva Mesin {selectedMachine})
        </button>
        <button
          onClick={() => setActiveTab('archive')}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors ${
            activeTab === 'archive'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
          }`}
        >
          <Clock className="h-4 w-4" />
          Archive (Riwayat Batch Sebelumnya)
        </button>
      </div>

      {/* METRIC CARDS RIBBON */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between text-gray-500 text-[11px]">
            <span>Suhu Aktual Bejana (PV)</span>
            <Flame className="h-4 w-4 text-danger" />
          </div>
          <h3 className="mt-1.5 text-xl font-extrabold text-danger font-mono">
            {liveData?.current_temp !== undefined ? `${liveData.current_temp} °C` : '-'}
          </h3>
          <span className="text-[10px] text-gray-400">Sensor Bejana Utama</span>
        </div>

        <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between text-gray-500 text-[11px]">
            <span>Setpoint Suhu (SP)</span>
            <Clock className="h-4 w-4 text-primary" />
          </div>
          <h3 className="mt-1.5 text-xl font-extrabold text-primary font-mono">
            {chartSeries[1]?.data?.slice(-1)[0] !== undefined ? `${chartSeries[1].data.slice(-1)[0]} °C` : '90.0 °C'}
          </h3>
          <span className="text-[10px] text-gray-400">Target Resep Saat Ini</span>
        </div>

        <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between text-gray-500 text-[11px]">
            <span>Batch & Program</span>
            <Play className="h-4 w-4 text-meta-3" />
          </div>
          <h3 className="mt-1.5 text-lg font-bold text-black dark:text-white font-mono truncate">
            #{liveData?.batch_no || '-'}
          </h3>
          <span className="text-[10px] text-meta-5 font-semibold truncate block">
            {liveData?.program_code ? `${liveData.program_code} (${liveData.program_name || ''})` : 'Program Standar'}
          </span>
        </div>

        <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
          <div className="flex items-center justify-between text-gray-500 text-[11px]">
            <span>Status Alarm HMI</span>
            <ShieldAlert className={`h-4 w-4 ${liveData?.is_alarm_active ? 'text-danger' : 'text-success'}`} />
          </div>
          <h3 className={`mt-1.5 text-sm font-bold ${liveData?.is_alarm_active ? 'text-danger' : 'text-success'}`}>
            {liveData?.is_alarm_active ? 'ALARM AKTIF!' : 'NORMAL / NO ALARM'}
          </h3>
          <span className="text-[10px] text-gray-400">
            {liveData?.is_alarm_active ? 'Periksa sensor atau intervensi' : 'Semua sensor normal'}
          </span>
        </div>

        <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-gray-500 text-[11px]">
            <span>TimescaleDB Points</span>
            <Database className="h-4 w-4 text-meta-5" />
          </div>
          <h3 className="mt-1.5 text-xl font-bold text-black dark:text-white font-mono">
            {chartCategories.length} Titik
          </h3>
          <span className="text-[10px] text-success font-semibold">Tersimpan Permanen</span>
        </div>
      </div>

      {/* TRACK 1: STEP TIMELINE BAR (UCStepState SETEX PARITY) */}
      <div className="rounded border border-stroke bg-white p-4 shadow-sm dark:border-strokedark dark:bg-boxdark space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="h-4 w-4 text-primary" />
            <h4 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider">
              Timeline Langkah Program Celup (SETEX Step State Synchronizer)
            </h4>
          </div>
          <span className="text-xs font-bold text-primary font-mono">
            Langkah Aktif: #{currentStepNo} ({stepsList.find(s => s.no === currentStepNo)?.name || 'Proses'})
          </span>
        </div>

        {/* Step Blocks */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 lg:grid-cols-8 gap-2 pt-1">
          {stepsList.map((st) => {
            const isActive = st.no === currentStepNo;
            const isCompleted = st.no < currentStepNo;
            return (
              <div
                key={st.no}
                className={`p-2.5 rounded border text-center transition-all ${
                  isActive
                    ? 'border-primary bg-primary/10 text-primary shadow-sm font-bold ring-2 ring-primary/20'
                    : isCompleted
                    ? 'border-success/40 bg-success/5 text-success font-medium'
                    : 'border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/30 text-gray-500'
                }`}
              >
                <div className="text-[10px] font-mono uppercase">Step #{st.no} [F{st.icon}]</div>
                <div className="text-xs font-semibold truncate mt-0.5">{st.name}</div>
                <div className="mt-1 text-[9px] font-bold">
                  {isActive ? '● SEDANG JALAN' : isCompleted ? '✓ SELESAI' : 'MENUNGGU'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* TRACK 2: MULTI-CHANNEL ANALOG CURVES (UCCurve PARITY) */}
      <div className="rounded border border-stroke bg-white p-5 shadow-sm dark:border-strokedark dark:bg-boxdark">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
              Profil Kurva Proses: Mesin {selectedMachine} (Batch #{liveData?.batch_no || '-'})
            </h4>
            <span className="text-xs text-gray-500">
              Sinkronisasi waktu nyata: Suhu PV, Setpoint SP, dan Sensor T2 (°C)
            </span>
          </div>
          <span className="text-xs text-gray-500 font-mono">
            Terakhir diperbarui: {lastUpdated}
          </span>
        </div>

        {chartSeries.length > 0 ? (
          <TempCurveChart
            series={chartSeries}
            categories={chartCategories}
            title={`Kurva Telemetri Kontroler SETEX Secom 777 - Batch #${liveData?.batch_no || ''}`}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            <Activity className="h-8 w-8 animate-pulse mb-2 text-primary" />
            <p className="text-sm font-medium">Sedang memuat data kurva dari mesin...</p>
          </div>
        )}
      </div>

      {/* TRACK 3 & 4: ALARMS & OPERATOR INTERVENTIONS (UCDocPanelAlarm) */}
      <div className="rounded border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark">
        {/* HEADER & DATE FILTER CONTROLS */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between py-3.5 px-6 border-b border-stroke dark:border-strokedark gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
                Riwayat Alarm & Intervensi HMI Mesin {selectedMachine}
              </h4>
              {selectedAlarmDate ? (
                <span className="text-[11px] bg-primary/10 text-primary font-bold px-2 py-0.5 rounded border border-primary/20 flex items-center gap-1">
                  <Calendar className="h-3 w-3" /> Tanggal: {selectedAlarmDate}
                </span>
              ) : (
                <span className="text-[11px] bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 font-semibold px-2 py-0.5 rounded border border-stroke dark:border-strokedark">
                  Semua Tanggal
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
              Penyaringan riwayat berdasarkan tanggal kejadian | Sumber: ALARMS.LOG & ALARM.ACT | PostgreSQL TimescaleDB
            </p>
          </div>

          {/* CONTROLS BERDASARKAN TANGGAL */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 bg-gray-50 dark:bg-meta-4/40 px-2.5 py-1.5 rounded border border-stroke dark:border-strokedark shadow-sm">
              <Calendar className="h-3.5 w-3.5 text-primary" />
              <span className="text-[11px] font-semibold text-gray-700 dark:text-gray-300">Pilih Tanggal:</span>
              <input
                type="date"
                value={selectedAlarmDate}
                onChange={(e) => setSelectedAlarmDate(e.target.value)}
                className="text-xs font-mono font-bold text-black dark:text-white bg-transparent outline-none cursor-pointer"
                title="Pilih tanggal kejadian alarm & intervensi HMI"
              />
              {selectedAlarmDate && (
                <button
                  onClick={() => setSelectedAlarmDate('')}
                  className="text-gray-400 hover:text-danger ml-1 p-0.5"
                  title="Hapus filter tanggal"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* QUICK PRESET BUTTONS */}
            <button
              onClick={() => {
                const today = new Date().toISOString().split('T')[0];
                setSelectedAlarmDate(today);
              }}
              className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${
                selectedAlarmDate === new Date().toISOString().split('T')[0]
                  ? 'bg-primary text-white border-primary shadow-xs'
                  : 'bg-white dark:bg-boxdark text-gray-700 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-100 dark:hover:bg-meta-4'
              }`}
            >
              Hari Ini
            </button>

            <button
              onClick={() => setSelectedAlarmDate('')}
              className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${
                !selectedAlarmDate
                  ? 'bg-primary text-white border-primary shadow-xs'
                  : 'bg-white dark:bg-boxdark text-gray-700 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-100 dark:hover:bg-meta-4'
              }`}
            >
              Semua Tanggal
            </button>

            {/* ORDER BY DATE TIME TOGGLE */}
            <button
              onClick={() => setAlarmSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm"
              title="Klik untuk mengubah urutan Date Time (Terbaru / Terlama)"
            >
              <ArrowUpDown className="h-3.5 w-3.5 text-primary" />
              <span className="text-[11px] text-gray-500">Order by:</span>
              <span className="font-bold text-primary font-mono text-[11px]">
                Date Time ({alarmSortOrder === 'desc' ? 'DESC ↓' : 'ASC ↑'})
              </span>
            </button>

            <button
              onClick={() => fetchAlarms()}
              disabled={alarmsLoading}
              className="p-1.5 rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-100 dark:hover:bg-meta-4 text-gray-600 dark:text-gray-300 shadow-sm"
              title="Segarkan Riwayat Alarm"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${alarmsLoading ? 'animate-spin text-primary' : ''}`} />
            </button>
          </div>
        </div>

        {/* SUB-BAR: KATEGORI & CHIPS TANGGAL TERSEDIA */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-2.5 bg-gray-50/60 dark:bg-meta-4/20 border-b border-stroke dark:border-strokedark text-xs">
          {/* TABS KATEGORI */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold text-gray-500 mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3" /> Filter Tipe:
            </span>
            <button
              onClick={() => setAlarmFilterCategory('ALL')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${
                alarmFilterCategory === 'ALL'
                  ? 'bg-primary text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Semua ({alarms.length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('ALARM')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${
                alarmFilterCategory === 'ALARM'
                  ? 'bg-amber-500 text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Alarm Sistem ({alarms.filter(a => !(a.is_intervention || ['0', '20', '256', '5899'].includes(String(a.alarm_code)))).length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('INTERVENTION')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${
                alarmFilterCategory === 'INTERVENTION'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Intervensi Operator ({alarms.filter(a => a.is_intervention || ['0', '20', '256', '5899'].includes(String(a.alarm_code))).length})
            </button>
          </div>

          {/* CHIPS TANGGAL CEPAT */}
          {availableAlarmDates.length > 0 && (
            <div className="flex items-center gap-1 overflow-x-auto py-0.5">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 mr-1">
                <CalendarDays className="h-3 w-3" /> Tanggal Arsip:
              </span>
              {availableAlarmDates.map((dt) => (
                <button
                  key={dt}
                  onClick={() => setSelectedAlarmDate(dt)}
                  className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold border transition-colors ${
                    selectedAlarmDate === dt
                      ? 'bg-primary text-white border-primary shadow-xs'
                      : 'bg-white dark:bg-boxdark border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:border-primary'
                  }`}
                  title={`Tampilkan riwayat tanggal ${dt}`}
                >
                  {dt}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* TABEL DATA (STRICT ORDER BY DATE TIME) */}
        <div className="p-4 overflow-x-auto">
          {alarms.length > 0 ? (
            (() => {
              // Pastikan data alarms terurut strictly berdasarkan Date Time sesuai alarmSortOrder
              const sortedAlarms = [...alarms].sort((a, b) => {
                const rawA = a.timestamp || a.alarm_timestamp || '';
                const rawB = b.timestamp || b.alarm_timestamp || '';
                const tA = rawA ? new Date(rawA.replace(' ', 'T')).getTime() : 0;
                const tB = rawB ? new Date(rawB.replace(' ', 'T')).getTime() : 0;
                return alarmSortOrder === 'asc' ? tA - tB : tB - tA;
              });

              return (
                <div className="space-y-3">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-stroke dark:border-strokedark text-gray-500">
                        <th 
                          onClick={() => setAlarmSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
                          className="py-2.5 px-4 font-bold cursor-pointer hover:bg-gray-100 dark:hover:bg-meta-4/40 select-none group transition-colors"
                          title="Klik untuk membalik urutan kronologis Tanggal & Waktu (Order By Date Time)"
                        >
                          <div className="flex items-center gap-1.5 text-black dark:text-white">
                            <span>Tanggal & Waktu Kejadian</span>
                            <div className="flex items-center text-primary">
                              {alarmSortOrder === 'desc' ? (
                                <ArrowDown className="h-3.5 w-3.5" />
                              ) : (
                                <ArrowUp className="h-3.5 w-3.5" />
                              )}
                              <span className="text-[10px] font-mono font-bold uppercase ml-0.5">
                                ({alarmSortOrder.toUpperCase()})
                              </span>
                            </div>
                          </div>
                        </th>
                        <th className="py-2.5 px-4 font-bold">Tipe Kejadian</th>
                        <th className="py-2.5 px-4 font-bold">Kode</th>
                        <th className="py-2.5 px-4 font-bold">Langkah / Step</th>
                        <th className="py-2.5 px-4 font-bold">Deskripsi Gangguan / Intervensi HMI</th>
                        <th className="py-2.5 px-4 font-bold">Tingkat Bahaya</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stroke dark:divide-strokedark">
                      {sortedAlarms.map((al, idx) => {
                        const isInterv = al.is_intervention || ['0', '20', '256', '5899'].includes(String(al.alarm_code));
                        const rawTs = al.timestamp || al.alarm_timestamp || '';
                        const [dPart, tPart] = rawTs.includes(' ') ? rawTs.split(' ') : [al.date || rawTs, al.time || ''];

                        return (
                          <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-meta-4/20 transition-colors">
                            <td className="py-2.5 px-4 font-mono">
                              <div className="flex flex-col">
                                <span className="font-bold text-black dark:text-white flex items-center gap-1">
                                  <Calendar className="h-3 w-3 text-primary inline" />
                                  {dPart}
                                </span>
                                <span className="text-[10px] text-gray-500">{tPart}</span>
                              </div>
                            </td>
                            <td className="py-2.5 px-4">
                              {isInterv ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                                  <UserCheck className="h-3 w-3" />
                                  INTERVENSI HMI
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                                  <AlertTriangle className="h-3 w-3" />
                                  ALARM SISTEM
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 px-4 font-bold font-mono">
                              <span className={isInterv ? 'text-blue-600 dark:text-blue-400' : 'text-danger'}>
                                {isInterv ? `HMI-${al.alarm_code}` : `ALR-${al.alarm_code}`}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 font-mono text-gray-600 dark:text-gray-300">
                              {al.step_no ? `Step #${al.step_no}` : '-'}
                            </td>
                            <td className="py-2.5 px-4 font-medium text-black dark:text-white">
                              <div>
                                {al.alarm_text || al.description || `Gangguan Kode #${al.alarm_code}`}
                                {al.batch_no && (
                                  <span className="ml-2 text-[10px] font-mono text-gray-400">
                                    (Batch: #{al.batch_no})
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-2.5 px-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                al.severity === 'CRITICAL' 
                                  ? 'bg-danger/10 text-danger border border-danger/20' 
                                  : al.severity === 'INFO'
                                  ? 'bg-success/10 text-success border border-success/20'
                                  : 'bg-warning/10 text-warning border border-warning/20'
                              }`}>
                                {al.severity || 'WARNING'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {/* FOOTER INFORMASI */}
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-[11px] text-gray-500 pt-2 border-t border-stroke dark:border-strokedark px-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span>
                        Menampilkan <strong className="text-black dark:text-white">{sortedAlarms.length}</strong> catatan
                        {selectedAlarmDate ? ` pada tanggal ${selectedAlarmDate}` : ' dari seluruh arsip'} untuk Mesin {selectedMachine}.
                      </span>
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                        ORDER BY: DATETIME ({alarmSortOrder.toUpperCase()})
                      </span>
                    </div>
                    {selectedAlarmDate && (
                      <button
                        onClick={() => setSelectedAlarmDate('')}
                        className="text-primary hover:underline font-semibold"
                      >
                        Tampilkan Semua Tanggal →
                      </button>
                    )}
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="text-center py-10 text-gray-400">
              <CheckCircle2 className="h-8 w-8 text-success mx-auto mb-2" />
              <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                {selectedAlarmDate
                  ? `Tidak ada riwayat alarm atau intervensi HMI Mesin ${selectedMachine} pada tanggal ${selectedAlarmDate}.`
                  : `Tidak ada catatan alarm aktif pada Mesin ${selectedMachine}.`}
              </p>
              {selectedAlarmDate && (
                <button
                  onClick={() => setSelectedAlarmDate('')}
                  className="mt-2 text-xs font-bold text-primary hover:underline inline-flex items-center gap-1"
                >
                  ← Reset Filter & Tampilkan Semua Tanggal
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Logs;
