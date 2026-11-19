import React, { useState, useEffect, useRef } from 'react';
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
  const isInitial797 = initialMachineFromUrl === 'DA01' || initialMachineFromUrl === 'M_95' || initialMachineFromUrl?.toUpperCase().includes('797');

  const [selectedMachine, setSelectedMachine] = useState(initialMachineFromUrl || '1A');
  const [machines, setMachines] = useState(['1A']);
  const [rawMachines, setRawMachines] = useState([]);
  const [hmiIp, setHmiIp] = useState(isInitial797 ? '192.168.1.95' : '172.16.110.101');
  const [refreshInterval, setRefreshInterval] = useState(3000); // 3 detik default realtime
  const [activeTab, setActiveTab] = useState('active'); // 'active' or 'archive'
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [liveData, setLiveData] = useState(null);
  const [chartSeries, setChartSeries] = useState([]);
  const [chartCategories, setChartCategories] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [lastUpdated, setLastUpdated] = useState('');
  const [selectedStepDetail, setSelectedStepDetail] = useState(null);

  const isFetchingRef = useRef(false);

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
          let fullList = [...data];
          if (!fullList.some(m => m.machine_no === 'DA01' || m.ip_address === '192.168.1.95')) {
            fullList.unshift({
              machine_no: 'DA01',
              display_name: 'SETEX 797CE Mesin DA01',
              group_name: 'Dyeing Sample / DA',
              controller_type: 'SETEX 797CE (Windows CE)',
              ip_address: '192.168.1.95',
              share_folder_path: '/Flashdisk/SC797CE',
            });
          }
          setRawMachines(fullList);
          const list = fullList.map((m) => m.machine_no);
          setMachines(list);
          const currentUrlParam = new URLSearchParams(window.location.search).get('machine');
          const targetMach = currentUrlParam && list.includes(currentUrlParam) ? currentUrlParam : (list.includes(selectedMachine) ? selectedMachine : list[0]);
          setSelectedMachine(targetMach);
          const matched = fullList.find((m) => m.machine_no === targetMach);
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
    if (isFetchingRef.current && !isManual) return;
    isFetchingRef.current = true;
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
      isFetchingRef.current = false;
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
    1: { name: 'Program Start', type: 'START', icon: '1' },
    2: { name: 'Fill', type: 'FILL', icon: '2' },
    713: { name: 'Fill Level', type: 'FILL', icon: '713' },
    85: { name: 'Dosing', type: 'DOSE', icon: '85' },
    86: { name: 'Dosing Chemical', type: 'DOSE', icon: '86' },
    126: { name: 'Check', type: 'CHECK', icon: '126' },
    127: { name: 'Check pH', type: 'CHECK', icon: '127' },
    141: { name: 'Temperature Control', type: 'HEAT', icon: '141' },
    121: { name: 'Holding', type: 'HOLD', icon: '121' },
    122: { name: 'Unload', type: 'UNLOAD', icon: '122' },
    131: { name: 'Cooling', type: 'COOL', icon: '131' },
    61: { name: 'Drain', type: 'DRAIN', icon: '61' },
    71: { name: 'Drain Percent', type: 'DRAIN', icon: '71' },
    144: { name: 'Runtime', type: 'RUNTIME', icon: '144' },
    237: { name: 'Inject AT1', type: 'INJECT', icon: '237' },
    238: { name: 'Inject AT2', type: 'INJECT', icon: '238' },
    261: { name: 'Load', type: 'LOAD', icon: '261' },
    710: { name: 'Rinse Time Mode', type: 'WASH', icon: '710' },
    714: { name: 'Washing', type: 'WASH', icon: '714' },
    938: { name: 'Dosing Progression 1', type: 'DOSE', icon: '938' },
    939: { name: 'Dosing Progression 2', type: 'DOSE', icon: '939' },
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
  const rawSteps = liveData?.steps && liveData.steps.length > 0 ? liveData.steps : null;

  const stepsList = rawSteps
    ? rawSteps.map(s => {
        // Real-time parity guarantee: if active step's func_id differs from live HMI function_code, auto-align
        if (s.no === currentStepNo && liveData?.function_code && s.func_id && Number(s.func_id) !== Number(liveData.function_code)) {
          const match = FUNCTION_MAP[liveData.function_code];
          if (match) {
            return { ...s, name: match.name, type: match.type, icon: String(liveData.function_code), func_id: liveData.function_code };
          }
        }
        return s;
      })
    : Array.from({ length: Math.max(7, currentStepNo) }, (_, i) => {
        const sNo = i + 1;
        if (sNo === currentStepNo && liveData?.function_code && FUNCTION_MAP[liveData.function_code]) {
          return { no: sNo, ...FUNCTION_MAP[liveData.function_code] };
        }
        const def = defaultCycleSteps.find(s => s.no === sNo);
        if (def) return def;
        return { no: sNo, name: `Langkah #${sNo}`, type: 'PROCESS', icon: '121' };
      });

  const is797 =
    hmiIp?.trim() === '192.168.1.95' ||
    selectedMachine === 'DA01' ||
    selectedMachine === 'M_95' ||
    selectedMachine?.toUpperCase().includes('797') ||
    liveData?.controller_type?.includes('797') ||
    rawMachines.find((m) => m.machine_no === selectedMachine)?.controller_type?.includes('797');

  const controllerName = is797 ? 'SETEX Secom 797CE' : 'SETEX Secom 777';
  const controllerFolder = is797
    ? '/Flashdisk/SC797CE/STATUS/STATUS.ACT'
    : '/Storage/sc777ce/STATUS/STATUS.ACT';

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
              {liveData?.database_mode === 'POSTGRES' ? 'Live TimescaleDB' : 'Database Lokal (SQLite Offline)'}
            </span>
            <span className="text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold px-2 py-0.5 rounded border border-blue-500/30">
              {controllerName}
            </span>
            {liveData?.is_live_hmi ? (
              <span className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/30 flex items-center gap-1.5" title={`Terhubung ke ${liveData.data_source}`}>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Live HMI ({liveData?.hmi_ip || hmiIp})
              </span>
            ) : (
              <span className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold px-2 py-0.5 rounded border border-amber-500/30 flex items-center gap-1.5" title={`Mode: ${liveData?.data_source || 'Storage Lokal'}`}>
                <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                Target: {hmiIp || (is797 ? '192.168.1.95' : '172.16.110.101')} (Offline/Fallback)
              </span>
            )}
          </div>
          <p className="text-xs text-body dark:text-gray-400 mt-1">
            Visualisasi kurva telemetri langsung dari HMI {controllerName} (<code className="text-primary font-mono font-bold">ftp://{hmiIp || (is797 ? '192.168.1.95' : '172.16.110.101')}{controllerFolder}</code>)
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
              placeholder={is797 ? '192.168.1.95' : '172.16.110.101'}
              className="text-xs font-mono font-bold text-black dark:text-white bg-transparent outline-none w-28"
              title={`IP Address Controller ${controllerName} (Port FTP 21)`}
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
                } else if (val === 'DA01' || val === 'M_95') {
                  setHmiIp('192.168.1.95');
                }
              }}
              className="text-xs font-bold text-black dark:text-white bg-transparent outline-none cursor-pointer max-w-[240px]"
            >
              {rawMachines.map((m) => {
                const isItem797 = m.machine_no === 'DA01' || m.machine_no === 'M_95' || m.ip_address === '192.168.1.95' || m.controller_type?.includes('797');
                const badge = isItem797 ? 'SETEX 797CE' : (m.controller_type?.includes('777') ? 'SETEX 777' : (m.controller_type || 'SETEX'));
                return (
                  <option key={m.machine_no} value={m.machine_no} className="dark:bg-boxdark">
                    {m.machine_no} - {m.display_name || `Mesin ${m.machine_no}`} ({badge})
                  </option>
                );
              })}
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
            {syncing ? 'Menyimpan ke DB...' : (liveData?.database_mode === 'POSTGRES' ? 'Sinkron ke Postgres' : 'Sinkron ke DB Lokal')}
          </button>
        </div>
      </div>

      {/* TABS: ACTIVE BATCH VS ARCHIVE (ORGATEX WORKPLACE PARITY) */}
      <div className="flex border-b border-stroke dark:border-strokedark">
        <button
          onClick={() => setActiveTab('active')}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors ${activeTab === 'active'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
            }`}
        >
          <Activity className="h-4 w-4" />
          Active Batch (Live Kurva Mesin {selectedMachine})
        </button>
        <button
          onClick={() => setActiveTab('archive')}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors ${activeTab === 'archive'
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
            <span>{liveData?.database_mode === 'POSTGRES' ? 'TimescaleDB Points' : 'Poin Database Lokal'}</span>
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sliders className="h-4 w-4 text-primary" />
            <h4 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider">
              Timeline Resep Program ({stepsList.length} Langkah Terdefinisi)
            </h4>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold text-primary font-mono bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
              Langkah Aktif: #{currentStepNo} ({stepsList.find(s => s.no === currentStepNo)?.name || 'Proses'})
            </span>
            <button
              onClick={() => {
                const active = stepsList.find(s => s.no === currentStepNo) || stepsList[0];
                if (active) setSelectedStepDetail(active);
              }}
              className="inline-flex items-center gap-1 text-[11px] font-bold bg-primary text-white hover:bg-primary/90 px-2.5 py-1 rounded shadow-xs transition-all active:scale-95 cursor-pointer"
              title="Klik untuk membuka tabel sub-step dan parameter langkah aktif"
            >
              Lihat Sub-Step #{currentStepNo}
            </button>
          </div>
        </div>

        {/* Step Blocks */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 lg:grid-cols-8 gap-2 pt-1 max-h-56 overflow-y-auto pr-1">
          {stepsList.map((st) => {
            const isActive = st.no === currentStepNo;
            const isCompleted = st.no < currentStepNo;
            return (
              <div
                key={st.no}
                id={`step-card-${st.no}`}
                onClick={() => setSelectedStepDetail(st)}
                className={`p-2.5 rounded border text-center transition-all cursor-pointer hover:shadow-md hover:border-primary/80 group ${isActive
                  ? 'border-primary bg-primary/15 text-primary shadow-md font-bold ring-2 ring-primary/40 scale-[1.02]'
                  : isCompleted
                    ? 'border-success/40 bg-success/5 text-success font-medium'
                    : 'border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/30 text-gray-500 hover:text-black dark:hover:text-white'
                  }`}
                title={`Klik untuk melihat detail sub-step & parameter langkah #${st.no}`}
              >
                <div className="text-[10px] font-mono uppercase">Step #{st.no} [F{st.icon}]</div>
                <div className="text-xs font-semibold truncate mt-0.5" title={st.name}>{st.name}</div>
                {st.p1 && (
                  <div className="text-[10px] font-mono text-primary/80 truncate mt-0.5">
                    {st.p1} {st.p3 ? `• ${st.p3}` : ''}
                  </div>
                )}
                {st.has_intervention && (
                  <div className="text-[9px] font-bold text-amber-700 dark:text-amber-300 bg-amber-500/15 px-1 py-0.5 rounded border border-amber-500/30 mt-0.5 truncate" title={st.intervention_notes}>
                    ⚠️ Δ {st.delta_p1}
                  </div>
                )}
                <div className="mt-1 text-[9px] font-bold flex items-center justify-center gap-1">
                  <span>{isActive ? '● SEDANG JALAN' : isCompleted ? '✓ SELESAI' : 'MENUNGGU'}</span>
                  <span className="opacity-0 group-hover:opacity-100 text-[10px] transition-opacity">🔍</span>
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
              Profil Kurva Proses: Mesin {selectedMachine} {is797 ? '(SETEX 797CE)' : '(SETEX 777)'} (Batch #{liveData?.batch_no || '-'})
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
            title={`Kurva Telemetri Kontroler ${controllerName} - Batch #${liveData?.batch_no || ''}`}
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
              className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${selectedAlarmDate === new Date().toISOString().split('T')[0]
                ? 'bg-primary text-white border-primary shadow-xs'
                : 'bg-white dark:bg-boxdark text-gray-700 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-100 dark:hover:bg-meta-4'
                }`}
            >
              Hari Ini
            </button>

            <button
              onClick={() => setSelectedAlarmDate('')}
              className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${!selectedAlarmDate
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
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${alarmFilterCategory === 'ALL'
                ? 'bg-primary text-white'
                : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
                }`}
            >
              Semua ({alarms.length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('ALARM')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${alarmFilterCategory === 'ALARM'
                ? 'bg-amber-500 text-white'
                : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
                }`}
            >
              Alarm Sistem ({alarms.filter(a => !(a.is_intervention || ['0', '20', '256', '5899'].includes(String(a.alarm_code)))).length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('INTERVENTION')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${alarmFilterCategory === 'INTERVENTION'
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
                  className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold border transition-colors ${selectedAlarmDate === dt
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
          {alarms.length > 0 || (liveData?.interventions && liveData.interventions.length > 0) ? (
            (() => {
              // Merge alarms with recorded operator parameter interventions
              const rawEvents = [
                ...alarms,
                ...(liveData?.interventions || []).map(inv => ({
                  id: `inv-${inv.id}`,
                  timestamp: inv.timestamp,
                  alarm_code: 'SET-MOD',
                  alarm_text: inv.notes,
                  step_no: inv.step_no,
                  is_intervention: true,
                  category: 'INTERVENTION',
                  severity: 'WARNING'
                }))
              ];

              const filteredEvents = rawEvents.filter(ev => {
                if (alarmFilterCategory === 'ALARM') return !ev.is_intervention;
                if (alarmFilterCategory === 'INTERVENTION') return ev.is_intervention;
                return true;
              });

              // Pastikan data terurut strictly berdasarkan Date Time sesuai alarmSortOrder
              const sortedAlarms = filteredEvents.sort((a, b) => {
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
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${al.severity === 'CRITICAL'
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

      {/* MODAL POPUP: SETEX SECOM PROGRAM LIST & SUB-STEP DETAIL (PARITY WITH HMI POPUP) */}
      {selectedStepDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <div className="bg-[#e4e7eb] dark:bg-boxdark border-2 border-[#b0b8c1] dark:border-strokedark rounded-lg shadow-2xl w-full max-w-2xl overflow-hidden font-sans">

            {/* HMI Classic Window Header */}
            <div className="bg-gradient-to-r from-[#d2d8e0] via-[#e5e9f0] to-[#c8d0dc] dark:from-meta-4 dark:to-boxdark border-b border-[#a0a8b4] px-4 py-2.5 flex items-center justify-between shadow-inner">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold font-mono text-[#2c3e50] dark:text-white tracking-wide">
                  Program List {liveData?.program_code || '0342'} {liveData?.program_name || 'PROGRAM 30 MCT F'}
                </span>
                <span className="text-xs bg-primary/20 text-primary border border-primary/30 font-bold px-2 py-0.5 rounded font-mono">
                  Step #{String(selectedStepDetail.no).padStart(3, '0')}
                </span>
              </div>
              <button
                onClick={() => setSelectedStepDetail(null)}
                className="w-7 h-7 bg-red-600 hover:bg-red-700 active:scale-95 text-white font-bold rounded flex items-center justify-center shadow-md transition-all cursor-pointer"
                title="Tutup Popup"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Table Content (SETEX HMI Parity) */}
            <div className="p-4 bg-white dark:bg-boxdark">
              {selectedStepDetail.has_intervention && (
                <div className="mb-3 p-3 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700/60 flex items-center justify-between text-xs text-amber-900 dark:text-amber-200 shadow-xs animate-in fade-in">
                  <div className="flex items-center gap-2">
                    <span className="text-base">⚠️</span>
                    <div>
                      <div className="font-bold">Intervensi Operator Terdeteksi:</div>
                      <div>{selectedStepDetail.intervention_notes}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] uppercase font-bold text-amber-700 dark:text-amber-400">Penyimpangan (Δ)</div>
                    <div className="font-mono font-extrabold text-sm text-amber-700 dark:text-amber-300">{selectedStepDetail.delta_p1}</div>
                  </div>
                </div>
              )}

              <div className="border border-[#b8c2cc] dark:border-strokedark rounded overflow-hidden shadow-inner">
                <table className="w-full text-xs text-left">
                  <thead className="bg-[#e9ecef] dark:bg-meta-4 text-[#334155] dark:text-gray-200 uppercase font-bold border-b border-[#b8c2cc] dark:border-strokedark font-mono">
                    <tr>
                      <th className="py-2.5 px-3 w-16 text-center border-r border-[#b8c2cc] dark:border-strokedark">Step No</th>
                      <th className="py-2.5 px-3 border-r border-[#b8c2cc] dark:border-strokedark">Description</th>
                      <th className="py-2.5 px-3 w-24 text-center border-r border-[#b8c2cc] dark:border-strokedark">P1 Resep</th>
                      <th className="py-2.5 px-3 w-24 text-center border-r border-[#b8c2cc] dark:border-strokedark">P2</th>
                      <th className="py-2.5 px-3 w-20 text-center border-r border-[#b8c2cc] dark:border-strokedark">P3</th>
                      <th className="py-2.5 px-3 w-32 text-center">Aktual / Δ</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#d0d7de] dark:divide-strokedark font-sans">
                    {(selectedStepDetail.sub_steps && selectedStepDetail.sub_steps.length > 0
                      ? selectedStepDetail.sub_steps
                      : [{ line: 1, name: selectedStepDetail.name, p1: selectedStepDetail.p1, p2: selectedStepDetail.p2, p3: selectedStepDetail.p3, is_sub: false }]
                    ).map((line, idx) => {
                      const isMain = !line.is_sub && line.line === 1;
                      return (
                        <tr
                          key={idx}
                          className={`${isMain
                            ? 'bg-[#0052cc] text-white font-bold'
                            : idx % 2 === 0
                              ? 'bg-white dark:bg-boxdark text-black dark:text-white'
                              : 'bg-[#f8f9fa] dark:bg-meta-4/30 text-black dark:text-white'
                            } transition-colors`}
                        >
                          <td className={`py-2 px-3 text-center font-mono border-r ${isMain ? 'border-blue-400 font-extrabold text-sm' : 'border-[#d0d7de] dark:border-strokedark text-gray-400'}`}>
                            {isMain ? String(selectedStepDetail.no).padStart(3, '0') : ''}
                          </td>
                          <td className={`py-2 px-3 border-r ${isMain ? 'border-blue-400' : 'border-[#d0d7de] dark:border-strokedark'} ${line.is_sub ? 'pl-6 font-medium text-gray-700 dark:text-gray-300' : 'font-bold'}`}>
                            {line.name}
                          </td>
                          <td className={`py-2 px-3 text-center font-mono border-r ${isMain ? 'border-blue-400' : 'border-[#d0d7de] dark:border-strokedark'}`}>
                            {line.p1 || '-'}
                          </td>
                          <td className={`py-2 px-3 text-center font-mono border-r ${isMain ? 'border-blue-400' : 'border-[#d0d7de] dark:border-strokedark'}`}>
                            {line.p2 || '-'}
                          </td>
                          <td className={`py-2 px-3 text-center font-mono border-r ${isMain ? 'border-blue-400' : 'border-[#d0d7de] dark:border-strokedark'}`}>
                            {line.p3 || '-'}
                          </td>
                          <td className="py-2 px-3 text-center font-mono">
                            {line.has_delta ? (
                              <span className="inline-block px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 font-bold font-mono text-[11px] border border-amber-300 dark:border-amber-700">
                                {line.actual_p1} (Δ {line.delta_p1})
                              </span>
                            ) : isMain ? (
                              <span className="text-blue-100 text-[11px]">Sesuai Resep</span>
                            ) : (
                              <span className="text-gray-400 text-[11px]">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Status info bar */}
              <div className="mt-3 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                <div>
                  Kategori: <span className="font-bold uppercase text-primary font-mono">{selectedStepDetail.type || 'PROCESS'}</span> (Kode: F{selectedStepDetail.icon})
                </div>
                <div>
                  Status Langkah: <span className={`font-bold font-mono px-2 py-0.5 rounded text-[11px] ${selectedStepDetail.no === currentStepNo
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : selectedStepDetail.no < currentStepNo
                      ? 'bg-success/10 text-success border border-success/20'
                      : 'bg-gray-100 text-gray-500'
                    }`}>
                    {selectedStepDetail.no === currentStepNo ? 'SEDANG JALAN' : selectedStepDetail.no < currentStepNo ? 'SELESAI' : 'MENUNGGU'}
                  </span>
                </div>
              </div>
            </div>

            {/* Modal Footer with Step Navigator */}
            <div className="bg-[#f1f3f5] dark:bg-meta-4 px-4 py-3 border-t border-[#b8c2cc] dark:border-strokedark flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  disabled={selectedStepDetail.no <= 1}
                  onClick={() => {
                    const prev = stepsList.find(s => s.no === selectedStepDetail.no - 1);
                    if (prev) setSelectedStepDetail(prev);
                  }}
                  className="px-3 py-1.5 text-xs font-bold rounded border border-stroke bg-white hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed dark:bg-boxdark dark:border-strokedark text-black dark:text-white transition-all cursor-pointer"
                >
                  ← Step Sebelumnya
                </button>
                <button
                  disabled={selectedStepDetail.no >= stepsList.length}
                  onClick={() => {
                    const next = stepsList.find(s => s.no === selectedStepDetail.no + 1);
                    if (next) setSelectedStepDetail(next);
                  }}
                  className="px-3 py-1.5 text-xs font-bold rounded border border-stroke bg-white hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed dark:bg-boxdark dark:border-strokedark text-black dark:text-white transition-all cursor-pointer"
                >
                  Step Berikutnya →
                </button>
              </div>

              <button
                onClick={() => setSelectedStepDetail(null)}
                className="px-4 py-1.5 text-xs font-bold rounded bg-gray-600 hover:bg-gray-700 text-white transition-all cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Logs;
