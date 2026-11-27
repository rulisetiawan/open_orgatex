import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import TempCurveChart from '../components/Charts/TempCurveChart';
import { useToast } from '../context/ToastContext';
import { LiveElapsedText } from '../components/UI/LiveTimers';
import {
  LineChart,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Database,
  Flame,
  Play,
  Pause,
  Clock,
  PauseCircle,
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
  ArrowDown,
  ArrowLeft,
  Search
} from 'lucide-react';

const API_BASE = '/api';

// Helper untuk mendeteksi apakah suatu langkah resep memiliki target/setpoint suhu
const isStepWithTempSetpoint = (step) => {
  if (!step) return false;
  if (step.has_temp_target !== undefined) return Boolean(step.has_temp_target);
  const type = String(step.type || '').toUpperCase();
  if (['HEAT', 'COOL', 'HOLD', 'TEMP'].includes(type)) return true;
  if ([140, 141, 142, 145, 146, 121, 131, 150].includes(Number(step.func_id))) return true;
  if (typeof step.p1 === 'string' && step.p1.includes('°C')) return true;
  if (typeof step.p2 === 'string' && step.p2.includes('°C')) return true;
  if (Array.isArray(step.params) && step.params.some(p => p.unit === '°C' || (p.formatted && p.formatted.includes('°C')))) return true;
  if (Array.isArray(step.sub_steps) && step.sub_steps.some(sub => {
    const sType = String(sub.type || '').toUpperCase();
    if (['HEAT', 'COOL', 'HOLD', 'TEMP'].includes(sType)) return true;
    if ([140, 141, 142, 145, 146, 121, 131, 150].includes(Number(sub.func_id))) return true;
    if (typeof sub.p1 === 'string' && sub.p1.includes('°C')) return true;
    return Array.isArray(sub.params) && sub.params.some(p => p.unit === '°C' || (p.formatted && p.formatted.includes('°C')));
  })) return true;
  return false;
};

// Helper untuk mengekstrak target/setpoint suhu sejati dari resep (atau intervensi operator)
const getStepTargetTemp = (step) => {
  if (!step) return null;
  // 1. Cek parameter resep langsung dari step.p1 / step.p2 (Prioritas Ground-Truth Resep)
  if (typeof step.p1 === 'string' && step.p1.includes('°C')) {
    const m = step.p1.match(/[-+]?\d*\.?\d+/);
    if (m) return parseFloat(m[0]);
  }
  if (typeof step.p2 === 'string' && step.p2.includes('°C')) {
    const m = step.p2.match(/[-+]?\d*\.?\d+/);
    if (m) return parseFloat(m[0]);
  }
  // 2. Cek parameter resep terstruktur (params P1 - P6)
  if (Array.isArray(step.params)) {
    const tempParam = step.params.find(p => 
      p.unit === '°C' || 
      (p.name && (p.name.toLowerCase().includes('temp') || p.name.toLowerCase().includes('suhu'))) ||
      (p.formatted && p.formatted.includes('°C'))
    );
    if (tempParam && tempParam.value !== undefined && tempParam.value > 0) {
      return Number(tempParam.value);
    }
  }
  // 3. Cek sub_steps
  if (Array.isArray(step.sub_steps)) {
    for (const sub of step.sub_steps) {
      if (typeof sub.p1 === 'string' && sub.p1.includes('°C')) {
        const m = sub.p1.match(/[-+]?\d*\.?\d+/);
        if (m) return parseFloat(m[0]);
      }
      if (Array.isArray(sub.params)) {
        const subP = sub.params.find(p => 
          p.unit === '°C' || 
          (p.name && (p.name.toLowerCase().includes('temp') || p.name.toLowerCase().includes('suhu'))) ||
          (p.formatted && p.formatted.includes('°C'))
        );
        if (subP && subP.value !== undefined && subP.value > 0) {
          return Number(subP.value);
        }
      }
    }
  }
  // 4. Cek intervensi operator untuk suhu jika ada
  if (Array.isArray(step.interventions) && step.interventions.length > 0) {
    const tempInv = step.interventions.find(i => 
      ((i.parameter_name && i.parameter_name.toLowerCase().includes('temp')) ||
      (i.unit && i.unit.includes('°C'))) &&
      Math.abs(Number(i.value_after) - 76.8) > 0.05
    );
    if (tempInv && tempInv.value_after !== undefined && tempInv.value_after > 0) {
      return Number(tempInv.value_after);
    }
  }
  if (step.actual_p1 && step.has_intervention && !String(step.actual_p1).includes('76.8')) {
    const num = parseFloat(step.actual_p1);
    if (!isNaN(num) && num > 0) return num;
  }
  // 5. Cek telemetri sp jika fungsi memang memiliki target suhu
  if (isStepWithTempSetpoint(step) && step.telemetry?.sp !== undefined && step.telemetry?.sp !== null && step.telemetry.sp > 0 && Math.abs(step.telemetry.sp - 90.0) > 0.01 && Math.abs(step.telemetry.sp - 76.8) > 0.01) {
    return Number(step.telemetry.sp);
  }
  return null;
};

const Logs = ({ defaultTab = 'active' }) => {
  const { toast } = useToast();
  const alarmSectionRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = new URLSearchParams(location.search);
  const initialMachineFromUrl = searchParams.get('machine');
  const tabFromUrl = searchParams.get('tab') || defaultTab;
  const isInitial797 = initialMachineFromUrl === 'DA01' || initialMachineFromUrl === 'M_95' || initialMachineFromUrl?.toUpperCase().includes('797');

  const [selectedMachine, setSelectedMachine] = useState(initialMachineFromUrl || '1A');
  const [machines, setMachines] = useState(['1A']);
  const [rawMachines, setRawMachines] = useState([]);
  const [hmiIp, setHmiIp] = useState(isInitial797 ? '192.168.1.95' : '172.16.110.101');
  const [refreshInterval, setRefreshInterval] = useState(3000); // 3 detik default realtime
  const [activeTab, setActiveTab] = useState(tabFromUrl === 'archive' ? 'archive' : 'active');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [liveData, setLiveData] = useState(null);
  const [chartSeries, setChartSeries] = useState([]);
  const [chartCategories, setChartCategories] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [lastUpdated, setLastUpdated] = useState('');
  const [selectedStepDetail, setSelectedStepDetail] = useState(null);
  // State Pemilihan Langkah pada Grafik Trend (Realtime vs Statis)
  // Jika memilih langkah yang sudah selesai, trend otomatis TIDAK REALTIME (rekaman statis).
  // Jika memilih langkah yang sedang berlangsung (atau siklus utuh live), trend REALTIME.
  const [selectedTrendStep, setSelectedTrendStep] = useState(null); // null / 'ALL' / number step (1, 2, ...)
  const [trendViewMode, setTrendViewMode] = useState('STEP'); // 'STEP' (Fokus Step) atau 'FULL' (Siklus Utuh)

  // State Riwayat Batch Selesai (Archive)
  const [archiveBatches, setArchiveBatches] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveSearch, setArchiveSearch] = useState('');
  const [archiveFilterMach, setArchiveFilterMach] = useState('SEMUA');

  // State Live Register & Multi-Object Inspector (Port 50000)
  const [showIwModal, setShowIwModal] = useState(false);
  const [iwLoading, setIwLoading] = useState(false);
  const [iwDetail, setIwDetail] = useState(null);
  const [iwActiveTab, setIwActiveTab] = useState('1025_iw'); // 'overview', '1025_iw', '1009_set', '1010_act', '6_func', '1035_batch'
  const [iwShowAllRegisters, setIwShowAllRegisters] = useState(false);
  const [iwSearchFilter, setIwSearchFilter] = useState('');
  const [selectedArchiveBatch, setSelectedArchiveBatch] = useState(null);
  const [archiveDetailLoading, setArchiveDetailLoading] = useState(false);

  const isFetchingRef = useRef(false);

  // Filter Alarms & Intervensi HMI berdasarkan tanggal & Order By Date Time
  const [selectedAlarmDate, setSelectedAlarmDate] = useState('');
  const [alarmFilterCategory, setAlarmFilterCategory] = useState('ALL');
  const [alarmSortOrder, setAlarmSortOrder] = useState('desc'); // 'desc' (terbaru ke terlama) atau 'asc' (terlama ke terbaru)
  const [availableAlarmDates, setAvailableAlarmDates] = useState([]);
  const [alarmsLoading, setAlarmsLoading] = useState(false);

  // Scroll to Alarm section automatically when opened via /alarms route
  useEffect(() => {
    if (defaultTab === 'alarms' && alarmSectionRef.current) {
      const t = setTimeout(() => {
        alarmSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 250);
      return () => clearTimeout(t);
    }
  }, [defaultTab]);

  // Close open modals on Escape key
  useEffect(() => {
    if (!selectedStepDetail && !showIwModal) return;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (showIwModal) setShowIwModal(false);
        else if (selectedStepDetail) setSelectedStepDetail(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedStepDetail, showIwModal]);

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

        // Format chart series: ambil Sensor T1 saja & Setpoint (SP) hanya jika step memiliki target suhu
        if (data.curve && data.curve.length > 0) {
          const cats = data.curve.map((pt) => {
            const parts = pt.timestamp.split(' ');
            return parts[1] || pt.timestamp;
          });
          const pv = data.curve.map((pt) => pt.temp_pv);
          const currentSteps = data.steps || [];
          const sp = data.curve.map((pt) => {
            const step = currentSteps.find((s) => s.no === pt.step_no);
            if (step && !isStepWithTempSetpoint(step)) return null;
            const targetT = getStepTargetTemp(step);
            if (targetT !== null && targetT > 0) return targetT;
            return (pt.temp_sp !== undefined && pt.temp_sp !== null && pt.temp_sp > 0 && Math.abs(pt.temp_sp - 90.0) > 0.1) ? pt.temp_sp : null;
          });

          setChartCategories(cats);
          setChartSeries([
            { name: 'Suhu Aktual Bejana T1 (PV °C)', data: pv },
            { name: 'Setpoint Suhu (SP °C)', data: sp },
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

  // Mengambil data registri IW (Info Words / Objek 1025) via TCP Port 50000
  const fetchIwRegisters = async () => {
    if (!selectedMachine) return;
    setIwLoading(true);
    try {
      const q = hmiIp ? `?ip=${encodeURIComponent(hmiIp)}` : '';
      const res = await fetch(`${API_BASE}/logs/iw/${selectedMachine}${q}`);
      if (res.ok) {
        const d = await res.json();
        setIwDetail(d);
      }
    } catch (e) {
      console.error('Gagal mengambil data register IW:', e);
    } finally {
      setIwLoading(false);
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

  // Fetch Riwayat Batch yang sudah dikerjakan
  const fetchArchiveBatches = async (mach = archiveFilterMach, search = archiveSearch) => {
    setArchiveLoading(true);
    try {
      const q = new URLSearchParams();
      if (mach && mach !== 'SEMUA') q.append('machine_no', mach);
      if (search && search.trim()) q.append('search', search.trim());
      const res = await fetch(`${API_BASE}/logs/batch-history?${q.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setArchiveBatches(data.batches || []);
      }
    } catch (err) {
      console.error('Gagal mengambil riwayat batch:', err);
    } finally {
      setArchiveLoading(false);
    }
  };

  // Pilih dan buka analisis batch riwayat (tampilan identik dengan active batch)
  const handleSelectArchiveBatch = async (batchItem) => {
    setArchiveDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/logs/batch-detail/${batchItem.machine_no}/${batchItem.batch_ref_no}`);
      if (res.ok) {
        const detail = await res.json();
        setSelectedArchiveBatch(detail);
      } else {
        toast.error('Gagal memuat detail data riwayat batch.');
      }
    } catch (err) {
      console.error('Gagal mengambil detail riwayat batch:', err);
      toast.error('Terjadi kesalahan saat memuat detail batch.');
    } finally {
      setArchiveDetailLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'archive') {
      fetchArchiveBatches(archiveFilterMach, archiveSearch);
    }
  }, [activeTab, archiveFilterMach]);

  useEffect(() => {
    if (tabFromUrl === 'archive') {
      setActiveTab('archive');
    } else if (tabFromUrl === 'active' || tabFromUrl === 'alarms') {
      setActiveTab('active');
    }
  }, [tabFromUrl]);

  useEffect(() => {
    if (activeTab === 'active') {
      fetchLiveLog();
      if (refreshInterval > 0) {
        const interval = setInterval(() => {
          if (!document.hidden) fetchLiveLog();
        }, refreshInterval);
        return () => clearInterval(interval);
      }
    }
  }, [selectedMachine, hmiIp, refreshInterval, activeTab]);

  // Trigger manual sync
  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/logs/sync/${selectedMachine}`, { method: 'POST' });
      if (res.ok) {
        const syncRes = await res.json();
        toast.success(
          `Titik telemetri baru: ${syncRes.new_points_persisted} · Alarm baru: ${syncRes.new_alarms_persisted} (PostgreSQL TimescaleDB)`,
          { title: 'Sinkronisasi Selesai!' }
        );
        fetchLiveLog();
        fetchAlarms();
      }
    } catch (err) {
      toast.error(`Gagal sinkronisasi: ${err.message}`);
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

  const formatStepTime = (ts) => {
    if (!ts) return null;
    const s = String(ts).trim();
    const parts = s.split(' ');
    if (parts.length > 1) {
      return parts[1];
    }
    if (s.includes('T')) {
      return s.split('T')[1].substring(0, 8);
    }
    return s;
  };

  // Calculates live "Sudah berjalan berapa lama" in real-time
  const getElapsedDuration = (startTimeStr) => {
    if (!startTimeStr) return null;
    try {
      let startMs = 0;
      const str = String(startTimeStr).trim();
      if (str.includes(' ') || str.includes('T')) {
        startMs = new Date(str.replace(' ', 'T')).getTime();
      } else {
        const parts = str.split(':').map(Number);
        const d = new Date();
        d.setHours(parts[0] || 0, parts[1] || 0, parts[2] || 0, 0);
        startMs = d.getTime();
      }
      if (isNaN(startMs)) return null;
      const diffSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
      if (diffSec > 86400) return null;

      if (diffSec < 60) return `${diffSec} dtk`;
      const mins = Math.floor(diffSec / 60);
      const secs = diffSec % 60;
      if (mins < 60) {
        return secs > 0 ? `${mins} mnt ${secs} dtk` : `${mins} mnt`;
      }
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs} jam ${remMins} mnt`;
    } catch {
      return null;
    }
  };

  // Computes dynamic real-time remaining or overtime label for active step
  const getLiveRemainingText = (startTimeStr, targetMin) => {
    if (!startTimeStr || !targetMin) return null;
    try {
      let startMs = 0;
      const str = String(startTimeStr).trim();
      if (str.includes(' ') || str.includes('T')) {
        startMs = new Date(str.replace(' ', 'T')).getTime();
      } else {
        const parts = str.split(':').map(Number);
        const d = new Date();
        d.setHours(parts[0] || 0, parts[1] || 0, parts[2] || 0, 0);
        startMs = d.getTime();
      }
      if (isNaN(startMs)) return null;
      const elapsedSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
      const targetSec = Number(targetMin) * 60;
      if (elapsedSec > targetSec + 30) {
        const overMin = Math.floor((elapsedSec - targetSec) / 60);
        return { isOvertime: true, text: `⚠️ Molor +${overMin} mnt` };
      } else {
        const remSec = targetSec - elapsedSec;
        const remMin = Math.max(0, Math.ceil(remSec / 60));
        return { isOvertime: false, text: `⏱ Sisa ~${remMin} mnt` };
      }
    } catch {
      return null;
    }
  };

  const isArchiveMode = activeTab === 'archive' && Boolean(selectedArchiveBatch);
  const effectiveData = isArchiveMode ? selectedArchiveBatch : liveData;
  const effectiveMachine = isArchiveMode ? selectedArchiveBatch.machine_no : selectedMachine;
  const currentStepNo = isArchiveMode 
    ? (selectedArchiveBatch.current_step || selectedArchiveBatch.steps?.length || 1)
    : (liveData?.current_step || 1);

  // Derive telemetry timings from curve for extra resilience
  const curveSource = isArchiveMode ? (selectedArchiveBatch?.curve || []) : (liveData?.curve || []);
  const curveTimings = useMemo(() => {
    if (!curveSource || !Array.isArray(curveSource)) return {};
    const map = {};
    for (const pt of curveSource) {
      if (pt.step_no && pt.timestamp) {
        const sNo = Number(pt.step_no);
        if (!map[sNo]) {
          map[sNo] = { start: pt.timestamp, end: pt.timestamp };
        } else {
          if (pt.timestamp < map[sNo].start) map[sNo].start = pt.timestamp;
          if (pt.timestamp > map[sNo].end) map[sNo].end = pt.timestamp;
        }
      }
    }
    return map;
  }, [curveSource]);

  const rawSteps = effectiveData?.steps && effectiveData.steps.length > 0 ? effectiveData.steps : null;

  const stepsList = rawSteps
    ? rawSteps.map(s => {
        let stepObj = { ...s };

        // Extract planned duration in minutes if not already set
        let targetMin = stepObj.target_min || null;
        if (!targetMin) {
          for (const p of [stepObj.p3, stepObj.p1, stepObj.p2]) {
            if (p) {
              const m = String(p).match(/(\d+)\s*(?:min|dak|mnt)/i);
              if (m && Number(m[1]) > 0) {
                targetMin = Number(m[1]);
                break;
              }
            }
          }
        }
        stepObj.target_min = targetMin;

        if (isArchiveMode) {
          stepObj.time_status = 'ON_TRACK';
          if (!stepObj.delta_text) stepObj.delta_text = '✓ Selesai';
        } else {
          // If step is in the future (WAITING), STRICTLY prevent any stale timing leaks
          if (s.no > currentStepNo) {
            stepObj.start_time = null;
            stepObj.end_time = null;
            stepObj.duration_text = null;
            stepObj.time_status = 'WAITING';
            stepObj.delta_text = targetMin ? `Target: ${targetMin} min` : 'Variabel';
          } else {
            // Fallback timing from curve only for active or past steps
            const cTiming = curveTimings[s.no];
            if (!stepObj.start_time && cTiming?.start) {
              stepObj.start_time = cTiming.start;
              if (s.no < currentStepNo && cTiming.end) {
                stepObj.end_time = cTiming.end;
              }
            }
          }

          // Real-time parity: Only auto-align if step has NO valid recipe function or is a generic placeholder
          if (s.no === currentStepNo && liveData?.function_code && (!s.func_id || s.func_id === 0 || s.name?.startsWith('Langkah #') || s.name?.startsWith('Step #'))) {
            const match = FUNCTION_MAP[liveData.function_code];
            if (match) {
              stepObj = { ...stepObj, name: match.name, type: match.type, icon: String(liveData.function_code), func_id: liveData.function_code };
            }
          }
        }
        return stepObj;
      })
    : Array.from({ length: Math.max(7, currentStepNo) }, (_, i) => {
        const sNo = i + 1;
        const cTiming = sNo <= currentStepNo ? curveTimings[sNo] : null;
        let base = {
          no: sNo,
          start_time: sNo <= currentStepNo ? (cTiming?.start || null) : null,
          end_time: sNo < currentStepNo ? (cTiming?.end || null) : null,
          time_status: isArchiveMode ? 'COMPLETED' : (sNo === currentStepNo ? 'RUNNING' : (sNo < currentStepNo ? 'COMPLETED' : 'WAITING')),
          delta_text: isArchiveMode ? '✓ Selesai' : undefined
        };
        if (!isArchiveMode && sNo === currentStepNo && liveData?.function_code && FUNCTION_MAP[liveData.function_code]) {
          return { ...base, ...FUNCTION_MAP[liveData.function_code] };
        }
        const def = defaultCycleSteps.find(s => s.no === sNo);
        if (def) return { ...base, ...def };
        return { ...base, name: `Langkah #${sNo}`, type: 'PROCESS', icon: '121' };
      });

  const activeStep = stepsList.find(s => s.no === currentStepNo);
  const activeStepElapsed = (!isArchiveMode && activeStep?.start_time) ? getElapsedDuration(activeStep.start_time) : null;
  const firstStepWithStart = stepsList.find(s => s.start_time);
  const batchTotalElapsed = isArchiveMode 
    ? (selectedArchiveBatch?.duration_text || null)
    : (firstStepWithStart?.start_time ? getElapsedDuration(firstStepWithStart.start_time) : null);

  // Evaluasi apakah grafik trend saat ini berstatus REALTIME atau STATIS
  // Ketentuan:
  // - Jika user memilih step yang sudah selesai (step yang sudah dilakukan): otomatis trend TIDAK REALTIME (rekaman kurva statis).
  // - Jika user memilih step yang sedang berlangsung (atau siklus utuh live): trend REALTIME.
  const isRealtimeTrend = useMemo(() => {
    if (isArchiveMode) return false;
    if (!selectedTrendStep || selectedTrendStep === 'ALL') return true;
    return Number(selectedTrendStep) === Number(currentStepNo);
  }, [isArchiveMode, selectedTrendStep, currentStepNo]);

  // Titik telemetri kurva aktif berdasarkan langkah terpilih dan mode tampilan (Fokus Step vs Siklus Utuh)
  const activeCurvePoints = useMemo(() => {
    const rawCurve = isArchiveMode ? (selectedArchiveBatch?.curve || []) : (liveData?.curve || []);
    if (!rawCurve || rawCurve.length === 0) return [];

    if (selectedTrendStep && selectedTrendStep !== 'ALL' && trendViewMode === 'STEP') {
      return rawCurve.filter((pt) => Number(pt.step_no) === Number(selectedTrendStep));
    }
    return rawCurve;
  }, [isArchiveMode, selectedArchiveBatch?.curve, liveData?.curve, selectedTrendStep, trendViewMode]);

  const displayChartCategories = useMemo(() => {
    if (activeCurvePoints.length > 0) {
      return activeCurvePoints.map((pt) => {
        const parts = (pt.timestamp || '').split(' ');
        return parts[1] || pt.timestamp;
      });
    }
    if (isArchiveMode && selectedArchiveBatch?.curve) {
      return selectedArchiveBatch.curve.map((pt) => {
        const parts = (pt.timestamp || '').split(' ');
        return parts[1] || pt.timestamp;
      });
    }
    if (!selectedTrendStep || selectedTrendStep === 'ALL' || Number(selectedTrendStep) === Number(currentStepNo)) {
      return chartCategories;
    }
    return [];
  }, [activeCurvePoints, isArchiveMode, selectedArchiveBatch?.curve, chartCategories, selectedTrendStep, currentStepNo]);

  const displayChartSeries = useMemo(() => {
    if (activeCurvePoints.length > 0) {
      const activeSteps = isArchiveMode 
        ? (selectedArchiveBatch?.steps || []) 
        : (liveData?.steps || stepsList || []);
      const pv = activeCurvePoints.map((pt) => pt.temp_pv);
      const sp = activeCurvePoints.map((pt) => {
        const step = activeSteps.find((s) => Number(s.no) === Number(pt.step_no));
        if (step && !isStepWithTempSetpoint(step)) return null;
        const targetT = getStepTargetTemp(step);
        if (targetT !== null && targetT > 0) return targetT;
        return (pt.temp_sp !== undefined && pt.temp_sp !== null && pt.temp_sp > 0 && Math.abs(pt.temp_sp - 90.0) > 0.1) ? pt.temp_sp : null;
      });
      return [
        { name: 'Suhu Aktual Bejana T1 (PV °C)', data: pv },
        { name: 'Setpoint Suhu (SP °C)', data: sp }
      ];
    }
    if (isArchiveMode && selectedArchiveBatch?.curve) {
      const archiveSteps = selectedArchiveBatch.steps || [];
      const pv = selectedArchiveBatch.curve.map((pt) => pt.temp_pv);
      const sp = selectedArchiveBatch.curve.map((pt) => {
        const step = archiveSteps.find((s) => Number(s.no) === Number(pt.step_no));
        if (step && !isStepWithTempSetpoint(step)) return null;
        const targetT = getStepTargetTemp(step);
        if (targetT !== null && targetT > 0) return targetT;
        return (pt.temp_sp !== undefined && pt.temp_sp !== null && pt.temp_sp > 0 && Math.abs(pt.temp_sp - 90.0) > 0.1) ? pt.temp_sp : null;
      });
      return [
        { name: 'Suhu Aktual Bejana T1 (PV °C)', data: pv },
        { name: 'Setpoint Suhu (SP °C)', data: sp }
      ];
    }
    if (!selectedTrendStep || selectedTrendStep === 'ALL' || Number(selectedTrendStep) === Number(currentStepNo)) {
      return chartSeries;
    }
    return [];
  }, [activeCurvePoints, isArchiveMode, selectedArchiveBatch?.curve, selectedArchiveBatch?.steps, liveData?.steps, stepsList, chartSeries, selectedTrendStep, currentStepNo]);

  // Indikator posisi batch saat ini pada grafik trend
  const chartAnnotations = useMemo(() => {
    if (!displayChartCategories || displayChartCategories.length === 0) return {};

    const xaxis = [];
    const points = [];

    // KASUS 1: GRAFIK TREND REALTIME (Langkah yang sedang berlangsung atau siklus utuh live)
    if (isRealtimeTrend) {
      const lastIndex = displayChartCategories.length - 1;
      const currentCategory = displayChartCategories[lastIndex];
      const currentPv = displayChartSeries[0]?.data?.[lastIndex] ?? effectiveData?.current_temp ?? 0;
      const currentStep = effectiveData?.current_step || currentStepNo || 1;

      // Cari rentang awal dan akhir step aktif pada kategori grafik (jika di mode siklus utuh)
      const currentCurve = liveData?.curve || [];
      const stepPts = currentCurve.filter((p) => Number(p.step_no) === Number(currentStep));
      let stepStartCat = null;
      let stepEndCat = null;
      if (stepPts.length > 0 && trendViewMode === 'FULL') {
        const firstTime = (stepPts[0].timestamp || '').split(' ')[1];
        const lastTime = (stepPts[stepPts.length - 1].timestamp || '').split(' ')[1];
        if (displayChartCategories.includes(firstTime)) stepStartCat = firstTime;
        if (displayChartCategories.includes(lastTime)) stepEndCat = lastTime;
      }

      // Shaded area untuk langkah proses yang sedang aktif
      if (stepStartCat && stepEndCat && stepStartCat !== stepEndCat) {
        xaxis.push({
          x: stepStartCat,
          x2: stepEndCat,
          fillColor: '#10b981',
          opacity: 0.12,
          label: {
            borderColor: '#10b981',
            style: {
              fontSize: '10px',
              color: '#ffffff',
              background: '#059669',
              fontWeight: 600,
              padding: { left: 4, right: 4, top: 2, bottom: 2 }
            },
            text: `Step #${currentStep} Sedang Berjalan (Realtime)`,
          }
        });
      }

      // Garis vertikal indikator posisi saat ini di grafik trend
      if (currentCategory) {
        xaxis.push({
          x: currentCategory,
          borderColor: '#10b981',
          strokeDashArray: 0,
          borderWidth: 2.5,
          label: {
            borderColor: '#10b981',
            orientation: 'horizontal',
            style: {
              color: '#ffffff',
              background: '#059669',
              fontSize: '11px',
              fontWeight: 700,
              padding: { left: 6, right: 6, top: 4, bottom: 4 }
            },
            text: `📍 Posisi Sekarang (Step #${currentStep} • ${currentPv}°C)`,
          }
        });

        // Pin marker bulat di titik PV saat ini
        points.push({
          x: currentCategory,
          y: currentPv,
          marker: {
            size: 8,
            fillColor: '#10b981',
            strokeColor: '#ffffff',
            strokeWidth: 3,
            shape: 'circle',
            radius: 3,
          },
          label: {
            borderColor: '#10b981',
            offsetY: -8,
            style: {
              color: '#ffffff',
              background: '#047857',
              fontSize: '11px',
              fontWeight: 700,
              padding: { left: 6, right: 6, top: 3, bottom: 3 }
            },
            text: `Saat Ini: ${currentPv}°C`,
          }
        });
      }

      return { xaxis, points };
    }

    // KASUS 2: GRAFIK TREND TIDAK REALTIME (Langkah yang sudah selesai dikerjakan / Statis)
    const targetStepNo = selectedTrendStep ? Number(selectedTrendStep) : (selectedStepDetail ? Number(selectedStepDetail.no) : null);
    if (!isRealtimeTrend && targetStepNo) {
      const stepObj = stepsList.find((s) => Number(s.no) === targetStepNo);
      const stepName = stepObj?.name || `Langkah #${targetStepNo}`;

      if (trendViewMode === 'STEP') {
        // Tampilan fokus langkah selesai: tandai waktu mulai dan waktu selesai
        if (displayChartCategories.length > 0) {
          const firstCat = displayChartCategories[0];
          const lastCat = displayChartCategories[displayChartCategories.length - 1];
          const lastPv = displayChartSeries[0]?.data?.[displayChartSeries[0]?.data?.length - 1];

          xaxis.push({
            x: firstCat,
            borderColor: '#64748b',
            strokeDashArray: 2,
            borderWidth: 1.5,
            label: {
              borderColor: '#64748b',
              style: { color: '#ffffff', background: '#475569', fontSize: '10px', fontWeight: 600 },
              text: `Mulai: ${firstCat}`,
            }
          });

          if (lastCat && lastCat !== firstCat) {
            xaxis.push({
              x: lastCat,
              borderColor: '#f59e0b',
              strokeDashArray: 2,
              borderWidth: 1.5,
              label: {
                borderColor: '#f59e0b',
                style: { color: '#ffffff', background: '#d97706', fontSize: '10px', fontWeight: 600 },
                text: `Selesai: ${lastCat} (${lastPv !== undefined ? `${lastPv}°C` : ''})`,
              }
            });
          }
        }
      } else {
        // Tampilan siklus utuh: sorot rentang langkah yang dipilih
        const rawCurve = isArchiveMode ? (selectedArchiveBatch?.curve || []) : (liveData?.curve || []);
        const stepPts = rawCurve.filter((p) => Number(p.step_no) === targetStepNo);
        if (stepPts.length > 0) {
          const startCat = (stepPts[0].timestamp || '').split(' ')[1];
          const endCat = (stepPts[stepPts.length - 1].timestamp || '').split(' ')[1];
          if (startCat) {
            xaxis.push({
              x: startCat,
              x2: endCat !== startCat ? endCat : undefined,
              borderColor: '#f59e0b',
              borderWidth: 2,
              fillColor: '#f59e0b',
              opacity: 0.15,
              label: {
                borderColor: '#f59e0b',
                style: {
                  color: '#ffffff',
                  background: '#d97706',
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: { left: 6, right: 6, top: 3, bottom: 3 }
                },
                text: `📁 Step #${targetStepNo}: ${stepName} (Selesai • Statis)`,
              }
            });
          }
        }
      }

      return { xaxis, points };
    }

    return {};
  }, [displayChartCategories, displayChartSeries, effectiveData, currentStepNo, isRealtimeTrend, selectedTrendStep, selectedStepDetail, trendViewMode, stepsList, liveData?.curve, selectedArchiveBatch?.curve, isArchiveMode]);

  const displayAlarms = useMemo(() => {
    if (isArchiveMode && selectedArchiveBatch?.alarms) {
      return selectedArchiveBatch.alarms;
    }
    return alarms;
  }, [isArchiveMode, selectedArchiveBatch?.alarms, alarms]);

  const is797 =
    hmiIp?.trim() === '192.168.1.95' ||
    effectiveMachine === 'DA01' ||
    effectiveMachine === 'M_95' ||
    effectiveMachine?.toUpperCase().includes('797') ||
    effectiveData?.controller_type?.includes('797') ||
    rawMachines.find((m) => m.machine_no === effectiveMachine)?.controller_type?.includes('797');

  const controllerName = is797 ? 'SETEX Secom 797CE' : 'SETEX Secom 777';
  const controllerFolder = is797
    ? '/Flashdisk/SC797CE/STATUS/STATUS.ACT'
    : '/Storage/sc777ce/STATUS/STATUS.ACT';

  return (
    <div className="space-y-6">
      {/* HEADER & TOOLBAR */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl md:text-2xl font-bold text-black dark:text-white">
              Process Analyser
            </h2>
            {liveData?.is_live_hmi ? (
              <span className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/30 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Live HMI ({liveData?.hmi_ip || hmiIp})
              </span>
            ) : (
              <span className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold px-2 py-0.5 rounded border border-amber-500/30 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                Offline
              </span>
            )}
          </div>
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

          {/* TOMBOL & INDIKATOR SETEX IW (TCP :50000) */}
          <button
            onClick={() => {
              setShowIwModal(true);
              fetchIwRegisters();
            }}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded border shadow-sm transition-all cursor-pointer ${
              liveData?.iw_telemetry?.online
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/25'
                : 'bg-white dark:bg-boxdark border-stroke dark:border-strokedark text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-meta-4'
            }`}
            title="Klik untuk membuka tabel Live Register IW (Info Words / Objek 1025) langsung via Port 50000"
          >
            <Activity className={`h-3.5 w-3.5 ${liveData?.iw_telemetry?.online ? 'text-emerald-500 animate-pulse' : 'text-gray-400'}`} />
            <span>SETEX IW (:50000)</span>
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold ${
              liveData?.iw_telemetry?.online ? 'bg-emerald-500 text-white' : 'bg-gray-200 text-gray-600 dark:bg-meta-4 dark:text-gray-300'
            }`}>
              {liveData?.iw_telemetry?.online ? 'LIVE' : 'SIAP'}
            </span>
          </button>

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

      {/* TABS: ACTIVE BATCH VS ARCHIVE */}
      <div className="flex border-b border-stroke dark:border-strokedark">
        <button
          onClick={() => {
            setActiveTab('active');
            setSelectedArchiveBatch(null);
          }}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors cursor-pointer ${activeTab === 'active'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
            }`}
        >
          <Activity className="h-4 w-4" />
          Batch Aktif ({selectedMachine})
        </button>
        <button
          onClick={() => {
            setActiveTab('archive');
            if (archiveBatches.length === 0) {
              fetchArchiveBatches(archiveFilterMach, archiveSearch);
            }
          }}
          className={`flex items-center gap-2 py-2 px-5 text-xs font-bold border-b-2 transition-colors cursor-pointer ${activeTab === 'archive'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
            }`}
        >
          <Clock className="h-4 w-4" />
          Riwayat Batch
          {archiveBatches.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-primary/10 text-primary border border-primary/20 font-mono font-bold ml-1">
              {archiveBatches.length}
            </span>
          )}
        </button>
      </div>

      {/* RIWAYAT BATCH (LIST OF COMPLETED BATCHES) */}
      {activeTab === 'archive' && !selectedArchiveBatch && (
        <div className="space-y-4">
          {/* SEARCH & FILTER CONTROLS */}
          <div className="rounded-xl border border-stroke bg-white p-4.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3.5">
              <div>
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Clock className="h-5 w-5 text-primary" />
                  Riwayat Batch Selesai
                </h3>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                {/* Filter Mesin */}
                <div className="flex items-center gap-2 bg-gray dark:bg-meta-4/60 px-3 py-1.5 rounded-lg border border-stroke dark:border-strokedark">
                  <Filter className="h-3.5 w-3.5 text-body" />
                  <span className="text-xs font-semibold text-body dark:text-bodydark">Mesin:</span>
                  <select
                    value={archiveFilterMach}
                    onChange={(e) => {
                      setArchiveFilterMach(e.target.value);
                      fetchArchiveBatches(e.target.value, archiveSearch);
                    }}
                    className="bg-transparent text-xs font-bold text-black dark:text-white outline-none cursor-pointer"
                  >
                    <option value="SEMUA" className="dark:bg-boxdark">Semua Mesin</option>
                    {machines.map((m) => (
                      <option key={m} value={m} className="dark:bg-boxdark">Mesin {m}</option>
                    ))}
                  </select>
                </div>

                {/* Search Bar */}
                <div className="relative min-w-[240px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-body" />
                  <input
                    type="text"
                    placeholder="Cari Batch, Resep, Customer..."
                    value={archiveSearch}
                    onChange={(e) => {
                      setArchiveSearch(e.target.value);
                      fetchArchiveBatches(archiveFilterMach, e.target.value);
                    }}
                    className="w-full pl-8.5 pr-8 py-1.5 text-xs bg-gray dark:bg-meta-4/60 border border-stroke dark:border-strokedark rounded-lg text-black dark:text-white outline-none focus:border-primary"
                  />
                  {archiveSearch && (
                    <button
                      onClick={() => {
                        setArchiveSearch('');
                        fetchArchiveBatches(archiveFilterMach, '');
                      }}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-body hover:text-black dark:hover:text-white"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>

                {/* Refresh Button */}
                <button
                  onClick={() => fetchArchiveBatches(archiveFilterMach, archiveSearch)}
                  disabled={archiveLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm transition-colors"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${archiveLoading ? 'animate-spin' : ''}`} />
                  Segarkan
                </button>
              </div>
            </div>
          </div>

          {/* LIST TABLE */}
          <div className="rounded-xl border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark overflow-hidden">
            {archiveLoading ? (
              <div className="py-16 text-center text-body">
                <RefreshCw className="h-8 w-8 mx-auto animate-spin text-primary mb-2" />
                <p className="text-sm font-semibold text-black dark:text-white">Memuat daftar riwayat batch...</p>
                <p className="text-xs text-body mt-0.5">Mengambil data dari PostgreSQL TimescaleDB</p>
              </div>
            ) : archiveBatches.length === 0 ? (
              <div className="py-16 text-center text-body">
                <Clock className="h-10 w-10 mx-auto text-body/40 mb-2" />
                <p className="text-sm font-bold text-black dark:text-white">Tidak ada riwayat batch ditemukan.</p>
                <p className="text-xs text-body mt-1">Coba ubah kata kunci pencarian atau filter mesin.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/40 text-[11px] font-bold text-body dark:text-bodydark uppercase tracking-wider">
                      <th className="py-3 px-4">Nomor Batch / Lot</th>
                      <th className="py-3 px-4">Mesin</th>
                      <th className="py-3 px-4">Resep / Program</th>
                      <th className="py-3 px-4">Customer & Artikel</th>
                      <th className="py-3 px-4">Waktu Pengerjaan</th>
                      <th className="py-3 px-4 text-center">Durasi & Telemetri</th>
                      <th className="py-3 px-4 text-center">Suhu Max</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-center">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stroke dark:divide-strokedark">
                    {archiveBatches.map((b, idx) => (
                      <tr
                        key={`${b.machine_no}_${b.batch_ref_no}_${idx}`}
                        onClick={() => handleSelectArchiveBatch(b)}
                        className="hover:bg-primary/5 dark:hover:bg-primary/10 transition-colors cursor-pointer group"
                      >
                        <td className="py-3 px-4 font-mono">
                          <span className="font-extrabold text-sm text-black dark:text-white block">
                            {b.batch_no}
                          </span>
                          <span className="text-[10px] text-body dark:text-bodydark block">
                            Ref #{b.batch_ref_no}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-primary/10 text-primary dark:bg-primary/20 dark:text-secondary border border-primary/20">
                            Mesin {b.machine_no}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-bold text-black dark:text-white block truncate max-w-[200px]" title={b.recipe_name}>
                            {b.recipe_name}
                          </span>
                          <span className="text-[10px] text-body dark:text-bodydark font-mono block">
                            {b.program_code}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium text-black dark:text-white block truncate max-w-[180px]">
                            {b.customer}
                          </span>
                          <span className="text-[10px] text-body dark:text-bodydark block truncate max-w-[180px]">
                            {b.article !== '-' ? b.article : (b.color_name !== '-' ? b.color_name : '100% Cotton')}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-body dark:text-bodydark whitespace-nowrap">
                          <div className="flex items-center gap-1">
                            <span className="text-gray-400">Mulai:</span>
                            <span className="text-black dark:text-white font-medium">{b.start_time}</span>
                          </div>
                          <div className="flex items-center gap-1 mt-0.5">
                            <span className="text-gray-400">Selesai:</span>
                            <span className="text-black dark:text-white font-medium">{b.end_time}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-center font-mono">
                          <span className="font-bold text-emerald-600 dark:text-emerald-400 block text-xs">
                            {b.duration_text}
                          </span>
                          <span className="text-[10px] text-body block">
                            {b.total_points.toLocaleString()} Titik
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-mono">
                          <span className="font-bold text-rose-600 dark:text-rose-400 inline-flex items-center gap-1">
                            <Flame className="h-3 w-3" />
                            {b.max_temp} °C
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                            <CheckCircle2 className="h-3 w-3" />
                            Selesai
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectArchiveBatch(b);
                            }}
                            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded-lg shadow-sm group-hover:scale-105 transition-all"
                          >
                            Buka Analisis
                            <ChevronRight className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* LOADING SPINNER WHEN FETCHING ARCHIVE BATCH DETAIL */}
      {activeTab === 'archive' && archiveDetailLoading && (
        <div className="py-24 text-center rounded-xl border border-stroke bg-white shadow-sm dark:border-strokedark dark:bg-boxdark">
          <RefreshCw className="h-10 w-10 mx-auto animate-spin text-primary mb-3" />
          <h3 className="text-base font-bold text-black dark:text-white">Memuat Data Analisis & Kurva Batch...</h3>
          <p className="text-xs text-body dark:text-bodydark mt-1">Mengambil telemetri, langkah resep, dan log alarm dari PostgreSQL TimescaleDB</p>
        </div>
      )}

      {/* ACTIVE BATCH VIEW OR SELECTED ARCHIVE BATCH DETAIL VIEW */}
      {(activeTab === 'active' || (activeTab === 'archive' && selectedArchiveBatch && !archiveDetailLoading)) && (
        <>
          {isArchiveMode && (
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 bg-primary/10 border border-primary/20 rounded-xl">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelectedArchiveBatch(null)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-lg hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white shadow-sm transition-all"
                >
                  <ArrowLeft className="h-4 w-4 text-primary" />
                  Kembali ke Daftar Riwayat Batch
                </button>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold text-primary dark:text-secondary uppercase tracking-wider">
                      Arsip Batch Selesai
                    </span>
                    <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                      {selectedArchiveBatch.batch_no}
                    </span>
                    <span className="text-xs text-body dark:text-bodydark font-semibold">
                      (Mesin {selectedArchiveBatch.machine_no})
                    </span>
                  </div>
                  <p className="text-[11px] text-body dark:text-bodydark mt-0.5 font-medium">
                    Mulai: <span className="font-mono text-black dark:text-white">{selectedArchiveBatch.start_time}</span> • Selesai: <span className="font-mono text-black dark:text-white">{selectedArchiveBatch.end_time}</span> • Durasi: <span className="font-mono font-bold text-emerald-600">{selectedArchiveBatch.duration_text}</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700/50 flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  SELESAI (COMPLETED)
                </span>
              </div>
            </div>
          )}

          {/* METRIC CARDS RIBBON */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
            <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
              <div className="flex items-center justify-between text-gray-500 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span>Suhu Bejana T1 (PV)</span>
                  {effectiveData?.iw_source && (
                    <span className="text-[9px] font-bold text-emerald-600 bg-emerald-500/10 px-1 py-0.2 rounded border border-emerald-500/20">
                      ⚡ IW 50000
                    </span>
                  )}
                </div>
                <Flame className="h-4 w-4 text-danger" />
              </div>
              <h3 className="mt-1.5 text-xl font-extrabold text-danger font-mono">
                {effectiveData?.current_temp !== undefined ? `${effectiveData.current_temp} °C` : '-'}
              </h3>
              <span className="text-[10px] text-gray-400">{isArchiveMode ? 'Suhu Puncak / Akhir' : (effectiveData?.iw_source ? 'Sensor IW Objek 1025' : 'Sensor Bejana Utama T1')}</span>
            </div>

            <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
              <div className="flex items-center justify-between text-gray-500 text-[11px]">
                <span>Setpoint Suhu (SP)</span>
                <Clock className="h-4 w-4 text-primary" />
              </div>
              <h3 className="mt-1.5 text-xl font-extrabold text-primary font-mono">
                {(() => {
                  const activeStepNum = effectiveData?.current_step || currentStepNo;
                  const activeSt = stepsList.find((s) => s.no === activeStepNum);
                  if (!activeSt || !isStepWithTempSetpoint(activeSt)) {
                    return '-';
                  }
                  const stTarget = getStepTargetTemp(activeSt);
                  if (stTarget !== null && stTarget > 0) {
                    return `${stTarget} °C`;
                  }
                  if (effectiveData?.current_sp !== undefined && effectiveData.current_sp > 0 && Math.abs(effectiveData.current_sp - 90.0) > 0.1) {
                    return `${effectiveData.current_sp} °C`;
                  }
                  return '-';
                })()}
              </h3>
              <span className="text-[10px] text-gray-400">
                {(() => {
                  const activeStepNum = effectiveData?.current_step || currentStepNo;
                  const activeSt = stepsList.find((s) => s.no === activeStepNum);
                  if (!activeSt || !isStepWithTempSetpoint(activeSt)) {
                    return 'Tanpa Target Suhu';
                  }
                  return `Target Step #${activeSt.no} (${activeSt.name})`;
                })()}
              </span>
            </div>

            <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
              <div className="flex items-center justify-between text-gray-500 text-[11px]">
                <span>Batch & Program</span>
                <Play className="h-4 w-4 text-meta-3" />
              </div>
              <div className="flex items-center justify-between gap-1 mt-1.5">
                <h3 className="text-lg font-bold text-black dark:text-white font-mono truncate">
                  #{effectiveData?.batch_no || '-'}
                </h3>
                {effectiveData?.program_code && (
                  <button
                    type="button"
                    onClick={() => {
                      if (effectiveMachine) {
                        localStorage.setItem('selected_dyeing_machine', effectiveMachine);
                      }
                      navigate(`/programs?prg=${encodeURIComponent(effectiveData.program_code)}`);
                    }}
                    className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25 border border-amber-500/30 transition-all flex items-center gap-1 cursor-pointer"
                    title="Buka dan edit program ini di Program Studio"
                  >
                    ✏️ Edit
                  </button>
                )}
              </div>
              <span className="text-[10px] text-meta-5 font-semibold truncate block">
                {effectiveData?.program_code ? `${effectiveData.program_code} (${effectiveData.program_name || effectiveData.recipe_name || ''})` : 'Program Standar'}
              </span>
            </div>

            <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark">
              <div className="flex items-center justify-between text-gray-500 text-[11px]">
                <span>Status Alarm HMI</span>
                <ShieldAlert className={`h-4 w-4 ${isArchiveMode ? 'text-success' : (effectiveData?.is_alarm_active ? 'text-danger' : 'text-success')}`} />
              </div>
              <h3 className={`mt-1.5 text-sm font-bold ${isArchiveMode ? 'text-success' : (effectiveData?.is_alarm_active ? 'text-danger' : 'text-success')}`}>
                {isArchiveMode ? 'NORMAL / SELESAI' : (effectiveData?.is_alarm_active ? 'ALARM AKTIF!' : 'NORMAL / NO ALARM')}
              </h3>
              <span className="text-[10px] text-gray-400">
                {isArchiveMode ? `${displayAlarms.length} Alarm Tercatat Selama Proses` : (effectiveData?.is_alarm_active ? 'Periksa sensor atau intervensi' : 'Semua sensor normal')}
              </span>
            </div>

            <div className="rounded border border-stroke bg-white p-3.5 shadow-sm dark:border-strokedark dark:bg-boxdark col-span-2 md:col-span-1">
              <div className="flex items-center justify-between text-gray-500 text-[11px]">
                <span>{effectiveData?.database_mode === 'POSTGRES' ? 'TimescaleDB Points' : 'Poin Database Lokal'}</span>
                <Database className="h-4 w-4 text-meta-5" />
              </div>
              <h3 className="mt-1.5 text-xl font-bold text-black dark:text-white font-mono">
                {effectiveData?.total_points || displayChartCategories.length} Titik
              </h3>
              <span className="text-[10px] text-success font-semibold">
                {isArchiveMode ? 'Arsip Selesai' : 'Tersimpan Permanen'}
              </span>
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
            <button
              onClick={() => setSelectedTrendStep('ALL')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all flex items-center gap-1 cursor-pointer ${
                selectedTrendStep === 'ALL'
                  ? 'bg-primary text-white shadow-xs'
                  : 'bg-gray-100 dark:bg-meta-4 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-meta-4/80'
              }`}
              title="Tampilkan seluruh siklus langkah pada kurva trend"
            >
              📊 Semua Langkah
            </button>
            <button
              onClick={() => setSelectedTrendStep(currentStepNo)}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                (!selectedTrendStep || Number(selectedTrendStep) === Number(currentStepNo))
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 border border-emerald-300 dark:border-emerald-700'
              }`}
              title="Tampilkan langkah yang sedang berjalan secara realtime"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse"></span>
              ⚡ Step Aktif #{currentStepNo} (Realtime)
            </button>
            <span className="text-xs font-bold text-primary font-mono bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
              Langkah Aktif: #{currentStepNo} ({stepsList.find(s => s.no === currentStepNo)?.name || 'Proses'})
            </span>
            {!isArchiveMode && activeStep?.start_time && (
              <span className="text-xs font-bold text-blue-700 dark:text-blue-300 font-mono bg-blue-500/10 px-2.5 py-0.5 rounded border border-blue-500/20 flex items-center gap-1.5" title="Durasi langkah aktif yang sedang berjalan saat ini">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
                <LiveElapsedText startTime={activeStep.start_time} prefix="Sudah Berjalan: " fallback="" />
              </span>
            )}
            {(isArchiveMode ? batchTotalElapsed : firstStepWithStart?.start_time) && (
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 font-mono bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/20 flex items-center gap-1" title="Total durasi proses batch sejak awal langkah">
                <Clock className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                {isArchiveMode ? (
                  <>Total Batch: {batchTotalElapsed}</>
                ) : (
                  <LiveElapsedText startTime={firstStepWithStart.start_time} prefix="Total Batch: " fallback="" />
                )}
              </span>
            )}
            <button
              onClick={() => {
                const targetStep = stepsList.find(s => s.no === (selectedTrendStep && selectedTrendStep !== 'ALL' ? Number(selectedTrendStep) : currentStepNo)) || stepsList[0];
                if (targetStep) setSelectedStepDetail(targetStep);
              }}
              className="inline-flex items-center gap-1 text-[11px] font-bold bg-primary text-white hover:bg-primary/90 px-2.5 py-1 rounded shadow-xs transition-all active:scale-95 cursor-pointer"
              title="Klik untuk membuka tabel sub-step dan parameter langkah terpilih"
            >
              Lihat Sub-Step #{selectedTrendStep && selectedTrendStep !== 'ALL' ? selectedTrendStep : currentStepNo}
            </button>
          </div>
        </div>

        {/* Step Blocks */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 lg:grid-cols-8 gap-2 pt-1 max-h-80 overflow-y-auto pr-1">
          {stepsList.map((st) => {
            const isActive = st.no === currentStepNo;
            const isCompleted = st.no < currentStepNo;
            const isSelectedForTrend = selectedTrendStep ? Number(selectedTrendStep) === Number(st.no) : isActive;
            return (
              <div
                key={st.no}
                id={`step-card-${st.no}`}
                onClick={() => setSelectedTrendStep(st.no)}
                className={`p-2 rounded border text-center transition-all cursor-pointer hover:shadow-md group relative ${
                  isSelectedForTrend
                    ? 'ring-2 ring-primary ring-offset-2 border-primary shadow-lg scale-[1.02] ' +
                      (isActive
                        ? 'bg-primary/15 text-primary font-bold'
                        : isCompleted
                          ? 'bg-amber-500/10 border-amber-500 ring-amber-500 text-amber-900 dark:text-amber-200 font-bold'
                          : 'bg-primary/10 text-primary font-bold')
                    : isActive
                      ? 'border-primary bg-primary/15 text-primary shadow-md font-bold'
                      : isCompleted
                        ? 'border-success/40 bg-success/5 text-success font-medium hover:border-success'
                        : 'border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/30 text-gray-500 hover:text-black dark:hover:text-white'
                }`}
                title={`Klik untuk menampilkan kurva ${st.name} pada grafik trend (${isCompleted ? 'Statis / Tidak Realtime' : isActive ? 'Live Realtime' : 'Menunggu'})`}
              >
                {/* Badge Status Pilihan Kurva */}
                {isSelectedForTrend && (
                  <div className="mb-1 text-[8px] font-bold uppercase tracking-wider">
                    {isCompleted ? (
                      <span className="bg-amber-500 text-white px-1.5 py-0.5 rounded-full shadow-2xs">
                        📈 Kurva Statis
                      </span>
                    ) : isActive ? (
                      <span className="bg-emerald-600 text-white px-1.5 py-0.5 rounded-full shadow-2xs animate-pulse">
                        📈 Kurva Realtime
                      </span>
                    ) : (
                      <span className="bg-gray-400 text-white px-1.5 py-0.5 rounded-full shadow-2xs">
                        📈 Antrean
                      </span>
                    )}
                  </div>
                )}

                <div className="text-[10px] font-mono uppercase">Step #{st.no} [F{st.icon}]</div>
                <div className="text-xs font-semibold truncate mt-0.5" title={st.name}>{st.name}</div>
                {st.comment && (
                  <div className="text-[9px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 rounded px-1 truncate mt-0.5" title={st.comment}>
                    📝 {st.comment}
                  </div>
                )}
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
                <div className="mt-1 text-[9px] font-bold flex items-center justify-center gap-1.5">
                  <span>{isActive ? '● SEDANG JALAN' : isCompleted ? '✓ SELESAI' : 'MENUNGGU'}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedStepDetail(st);
                    }}
                    className="p-0.5 hover:bg-black/10 dark:hover:bg-white/10 rounded transition-colors"
                    title="Buka tabel sub-step dan parameter"
                  >
                    🔍
                  </button>
                </div>

                {/* Execution Timing & Target Comparison */}
                <div className="mt-1.5 pt-1 border-t border-dashed border-gray-200 dark:border-strokedark text-[8.5px] font-mono text-left space-y-0.5">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Mulai:</span>
                    <span className="font-semibold text-gray-700 dark:text-gray-200">
                      {formatStepTime(st.start_time) || '-'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Selesai:</span>
                    <span className="font-semibold text-gray-700 dark:text-gray-200">
                      {isActive ? (
                        <span className="text-primary animate-pulse font-bold">Jalan...</span>
                      ) : (
                        formatStepTime(st.end_time) || '-'
                      )}
                    </span>
                  </div>
                  {isActive ? (
                    <div className="flex items-center justify-between text-[8.5px] bg-primary/10 px-1 py-0.5 rounded border border-primary/20">
                      <span className="text-primary font-bold">Sudah Jalan:</span>
                      <span className="font-mono font-extrabold text-primary">
                        {getElapsedDuration(st.start_time) || st.duration_text || 'Berjalan...'}
                      </span>
                    </div>
                  ) : st.duration_text ? (
                    <div className="flex items-center justify-between text-[8px] text-gray-400 dark:text-gray-500">
                      <span>Aktual:</span>
                      <span className="font-semibold text-gray-700 dark:text-gray-200">
                        {st.duration_text}
                      </span>
                    </div>
                  ) : null}

                  {/* Target vs Actual Deviation Badge */}
                  {isActive ? (
                    <div className="pt-0.5 text-center">
                      {(() => {
                        const liveRem = getLiveRemainingText(st.start_time, st.target_min);
                        if (liveRem) {
                          return (
                            <span className={`inline-block w-full px-1 py-0.5 rounded font-bold text-[8px] truncate border ${
                              liveRem.isOvertime
                                ? 'bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/40 animate-pulse'
                                : 'bg-primary/15 text-primary dark:text-blue-300 border-primary/30'
                            }`}>
                              {liveRem.text}
                            </span>
                          );
                        }
                        return (
                          <span className="inline-block w-full px-1 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary dark:text-blue-300 font-bold text-[8px] truncate">
                            ⏱ {st.delta_text || (st.target_min ? `Target: ${st.target_min} min` : 'Sedang Berjalan')}
                          </span>
                        );
                      })()}
                    </div>
                  ) : st.delta_text ? (
                    <div className="pt-0.5 text-center">
                      {st.time_status === 'SLOWER' || st.time_status === 'OVERTIME' ? (
                        <span className="inline-block w-full px-1 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-700 dark:text-rose-300 font-bold text-[8px] truncate" title="Proses lebih lambat / molor dari target resep">
                          ⚠️ {st.delta_text}
                        </span>
                      ) : st.time_status === 'FASTER' ? (
                        <span className="inline-block w-full px-1 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 font-bold text-[8px] truncate" title="Proses lebih cepat dari target resep">
                          ⚡ {st.delta_text}
                        </span>
                      ) : st.time_status === 'ON_TRACK' ? (
                        <span className="inline-block w-full px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium text-[8px] truncate">
                          ✓ Sesuai Target
                        </span>
                      ) : (
                        <span className="inline-block w-full text-gray-400 dark:text-gray-500 text-[8px] truncate">
                          {st.delta_text}
                        </span>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* TRACK 2: ANALOG CURVES (Sensor T1 Process Value & Target SP) */}
      <div className="rounded border border-stroke bg-white p-5 shadow-sm dark:border-strokedark dark:bg-boxdark">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
                Profil Kurva Proses: Mesin {effectiveMachine} {is797 ? '(SETEX 797CE)' : '(SETEX 777)'} (Batch #{effectiveData?.batch_no || '-'})
              </h4>

              {/* Status Indikator REALTIME vs STATIS */}
              {isArchiveMode ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 text-gray-700 dark:bg-meta-4 dark:text-gray-300 border border-stroke dark:border-strokedark">
                  <Database className="w-3 h-3 text-primary" /> ARSIP BATCH SELESAI
                </span>
              ) : isRealtimeTrend ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700 shadow-2xs">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  {selectedTrendStep && selectedTrendStep !== 'ALL'
                    ? `LIVE REALTIME: STEP #${currentStepNo}`
                    : `SIKLUS UTUH REALTIME (#${currentStepNo})`}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-700 shadow-2xs">
                  <Clock className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                  REKAMAN STATIS: STEP #{selectedTrendStep}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* View Mode Toggle: Fokus Step vs Siklus Utuh */}
            <div className="flex items-center bg-gray-100 dark:bg-meta-4 p-0.5 rounded border border-stroke dark:border-strokedark text-xs font-semibold">
              <button
                type="button"
                onClick={() => setTrendViewMode('STEP')}
                className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                  trendViewMode === 'STEP'
                    ? 'bg-white dark:bg-boxdark text-primary font-bold shadow-xs'
                    : 'text-gray-500 hover:text-black dark:hover:text-white'
                }`}
                title="Tampilkan hanya data titik langkah yang dipilih"
              >
                🔍 Fokus Step {selectedTrendStep && selectedTrendStep !== 'ALL' ? `#${selectedTrendStep}` : `#${currentStepNo}`}
              </button>
              <button
                type="button"
                onClick={() => setTrendViewMode('FULL')}
                className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                  trendViewMode === 'FULL'
                    ? 'bg-white dark:bg-boxdark text-primary font-bold shadow-xs'
                    : 'text-gray-500 hover:text-black dark:hover:text-white'
                }`}
                title="Tampilkan seluruh siklus batch dengan penanda langkah terpilih"
              >
                🌐 Siklus Utuh
              </button>
            </div>

            {/* Quick Action Button: Kembali ke Step Aktif jika sedang melihat langkah statis */}
            {!isRealtimeTrend && !isArchiveMode && (
              <button
                type="button"
                onClick={() => setSelectedTrendStep(currentStepNo)}
                className="px-2.5 py-1 rounded bg-primary text-white text-xs font-bold hover:bg-primary/90 flex items-center gap-1 shadow-xs transition-all active:scale-95 cursor-pointer"
                title="Beralih ke langkah aktif yang sedang berlangsung secara realtime"
              >
                ⚡ Step Aktif (Realtime)
              </button>
            )}

            {/* Indikator Status Waktu Refresh & Tombol Pause Realtime */}
            <div className="flex items-center gap-2 text-xs font-mono">
              {!isArchiveMode && (
                <button
                  type="button"
                  onClick={() => setRefreshInterval((prev) => (prev === 0 ? 3000 : 0))}
                  className={`px-2.5 py-1 rounded border flex items-center gap-1.5 font-sans font-bold text-xs transition-all cursor-pointer ${
                    refreshInterval === 0
                      ? 'bg-amber-500 hover:bg-amber-600 text-white border-amber-600 shadow-xs'
                      : 'bg-white dark:bg-boxdark hover:bg-gray-100 dark:hover:bg-meta-4 text-gray-700 dark:text-gray-200 border-stroke dark:border-strokedark shadow-xs'
                  }`}
                  title={refreshInterval === 0 ? 'Klik untuk melanjutkan pembaruan realtime' : 'Klik untuk menjeda pembaruan realtime'}
                >
                  {refreshInterval === 0 ? (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current text-white" />
                      <span>Resume Realtime</span>
                    </>
                  ) : (
                    <>
                      <Pause className="w-3.5 h-3.5 fill-current text-amber-500" />
                      <span>Pause Realtime</span>
                    </>
                  )}
                </button>
              )}

              {isArchiveMode ? (
                <span className="bg-gray-100 dark:bg-meta-4 px-2.5 py-1 rounded border border-stroke dark:border-strokedark font-medium text-gray-500">
                  Total: {displayChartCategories.length} Titik
                </span>
              ) : refreshInterval === 0 ? (
                <span className="bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 px-2.5 py-1 rounded flex items-center gap-1.5 font-medium">
                  <PauseCircle className="w-3.5 h-3.5 text-amber-500" />
                  Realtime Dijeda
                </span>
              ) : isRealtimeTrend ? (
                <span className="bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 px-2.5 py-1 rounded flex items-center gap-1.5 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  Terakhir: {lastUpdated} (Live)
                </span>
              ) : (
                <span className="bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 px-2.5 py-1 rounded flex items-center gap-1.5 font-medium">
                  <PauseCircle className="w-3.5 h-3.5 text-amber-500" />
                  Mode Statis (Bukan Realtime)
                </span>
              )}
            </div>
          </div>
        </div>

        {displayChartSeries.length > 0 && displayChartCategories.length > 0 ? (
          <TempCurveChart
            series={displayChartSeries}
            categories={displayChartCategories}
            annotations={chartAnnotations}
            title={
              isArchiveMode
                ? `Arsip Kurva Suhu T1 & Setpoint - Batch #${effectiveData?.batch_no || ''}${selectedTrendStep && selectedTrendStep !== 'ALL' ? ` (Step #${selectedTrendStep})` : ''}`
                : isRealtimeTrend
                  ? `Grafik Trend Suhu T1 & Posisi Batch Realtime - ${selectedTrendStep && selectedTrendStep !== 'ALL' ? `Step #${currentStepNo}` : `Batch #${effectiveData?.batch_no || ''}`}`
                  : `Rekaman Statis Suhu T1 & Setpoint (Tidak Realtime) - Step #${selectedTrendStep}: ${stepsList.find(s => Number(s.no) === Number(selectedTrendStep))?.name || ''}`
            }
          />
        ) : selectedTrendStep && Number(selectedTrendStep) > Number(currentStepNo) && !isArchiveMode ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 bg-gray-50/50 dark:bg-meta-4/20 rounded border border-dashed border-stroke dark:border-strokedark p-6 text-center">
            <Clock className="h-9 w-9 text-gray-400 mb-2" />
            <h5 className="text-sm font-bold text-gray-800 dark:text-gray-200">
              Step #{selectedTrendStep} ({stepsList.find(s => Number(s.no) === Number(selectedTrendStep))?.name || 'Proses'}) Belum Berjalan
            </h5>
            <p className="text-xs text-gray-500 mt-1 max-w-md">
              Langkah ini masih dalam antrean (Status: Menunggu). Rekaman kurva telemetri akan otomatis dimulai ketika mesin mengeksekusi langkah ini.
            </p>
            <button
              type="button"
              onClick={() => setSelectedTrendStep(currentStepNo)}
              className="mt-3 px-3 py-1.5 bg-primary text-white rounded text-xs font-bold hover:bg-primary/90 flex items-center gap-1.5 shadow-sm cursor-pointer"
            >
              ⚡ Tampilkan Step Berlangsung #{currentStepNo} (Realtime)
            </button>
          </div>
        ) : selectedTrendStep && Number(selectedTrendStep) < Number(currentStepNo) && !isArchiveMode ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 bg-gray-50/50 dark:bg-meta-4/20 rounded border border-dashed border-stroke dark:border-strokedark p-6 text-center">
            <AlertCircle className="h-9 w-9 text-amber-500 mb-2" />
            <h5 className="text-sm font-bold text-gray-800 dark:text-gray-200">
              Tidak Ada Titik Kurva untuk Step #{selectedTrendStep}
            </h5>
            <p className="text-xs text-gray-500 mt-1 max-w-md">
              Data kurva telemetri untuk langkah ini tidak ditemukan pada memori penyangga mesin saat ini.
            </p>
            <button
              type="button"
              onClick={() => setSelectedTrendStep(currentStepNo)}
              className="mt-3 px-3 py-1.5 bg-primary text-white rounded text-xs font-bold hover:bg-primary/90 flex items-center gap-1.5 shadow-sm cursor-pointer"
            >
              ⚡ Kembali ke Step Berlangsung #{currentStepNo} (Realtime)
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            {loading ? (
              <>
                <Activity className="h-7 w-7 animate-pulse mb-2 text-primary" />
                <p className="text-xs font-medium">Memuat kurva mesin...</p>
              </>
            ) : (
              <>
                <LineChart className="h-7 w-7 mb-2 text-gray-300 dark:text-gray-600" />
                <p className="text-xs font-medium">Belum ada rekaman titik kurva untuk proses ini</p>
              </>
            )}
          </div>
        )}
      </div>

      {/* TRACK 3 & 4: ALARMS & OPERATOR INTERVENTIONS (UCDocPanelAlarm) */}
      <div
        ref={alarmSectionRef}
        className={`rounded-xl border bg-white shadow-sm dark:bg-boxdark ${
          defaultTab === 'alarms'
            ? 'border-warning/60 ring-2 ring-warning/20'
            : 'border-stroke dark:border-strokedark'
        }`}
      >
        {/* HEADER & DATE FILTER CONTROLS */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between py-3.5 px-6 border-b border-stroke dark:border-strokedark gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              <h4 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">
                Alarm & Intervensi ({effectiveMachine})
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
              Semua ({displayAlarms.length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('ALARM')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${alarmFilterCategory === 'ALARM'
                ? 'bg-amber-500 text-white'
                : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
                }`}
            >
              Alarm Sistem ({displayAlarms.filter(a => !(a.is_intervention || ['0', '20', '256', '5899'].includes(String(a.alarm_code)))).length})
            </button>
            <button
              onClick={() => setAlarmFilterCategory('INTERVENTION')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-colors ${alarmFilterCategory === 'INTERVENTION'
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
                }`}
            >
              Intervensi Operator ({displayAlarms.filter(a => a.is_intervention || ['0', '20', '256', '5899'].includes(String(a.alarm_code))).length})
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
          {displayAlarms.length > 0 || (effectiveData?.interventions && effectiveData.interventions.length > 0) ? (
            (() => {
              // Merge alarms with recorded operator parameter interventions
              const rawEvents = [
                ...displayAlarms,
                ...(effectiveData?.interventions || []).map(inv => ({
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
                        {selectedAlarmDate ? ` pada tanggal ${selectedAlarmDate}` : ' dari seluruh arsip'} untuk Mesin {effectiveMachine}.
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
                  ? `Tidak ada riwayat alarm atau intervensi HMI Mesin ${effectiveMachine} pada tanggal ${selectedAlarmDate}.`
                  : `Tidak ada catatan alarm aktif pada Mesin ${effectiveMachine}.`}
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
      </>
      )}

      {/* MODAL POPUP: SETEX SECOM PROGRAM LIST & SUB-STEP DETAIL (PARITY WITH HMI POPUP) */}
      {selectedStepDetail && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Detail Langkah Program"
          onClick={() => setSelectedStepDetail(null)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark border border-stroke dark:border-strokedark rounded-xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden font-sans"
          >

            {/* HMI Classic Window Header */}
            <div className="bg-gray-100 dark:bg-meta-4 border-b border-stroke dark:border-strokedark px-4 py-3 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold font-mono text-black dark:text-white tracking-wide">
                  Program List {effectiveData?.program_code || ''} {effectiveData?.program_name || effectiveData?.recipe_name || ''}
                </span>
                <span className="text-xs bg-primary/10 text-primary dark:bg-primary/20 dark:text-secondary border border-primary/20 font-bold px-2 py-0.5 rounded-full font-mono">
                  Step #{String(selectedStepDetail.no).padStart(3, '0')}
                </span>
                <span className="text-[11px] bg-gray-200 dark:bg-boxdark font-bold font-mono px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">
                  Kategori: {selectedStepDetail.type || 'PROCESS'} [F{selectedStepDetail.icon}]
                </span>
                <span className={`text-[11px] font-bold font-mono px-2 py-0.5 rounded ${
                  selectedStepDetail.no === currentStepNo
                    ? 'bg-primary/15 text-primary border border-primary/30 animate-pulse'
                    : selectedStepDetail.no < currentStepNo
                      ? 'bg-success/15 text-success border border-success/30'
                      : 'bg-gray-100 text-gray-500'
                }`}>
                  {selectedStepDetail.no === currentStepNo ? 'SEDANG JALAN' : selectedStepDetail.no < currentStepNo ? 'SELESAI' : 'MENUNGGU'}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    const prgCode = effectiveData?.program_code || effectiveData?.program_no || '';
                    if (effectiveMachine) {
                      localStorage.setItem('selected_dyeing_machine', effectiveMachine);
                    }
                    navigate(`/programs${prgCode ? `?prg=${encodeURIComponent(prgCode)}` : ''}`);
                  }}
                  className="px-2.5 py-1 text-xs font-bold rounded bg-amber-500 hover:bg-amber-600 text-white transition-all flex items-center gap-1 shadow-xs cursor-pointer active:scale-95"
                  title="Buka atau edit program resep ini di Program Studio"
                >
                  ✏️ Edit Program
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTrendStep(selectedStepDetail.no);
                    setSelectedStepDetail(null);
                  }}
                  className="px-2.5 py-1 text-xs font-bold rounded bg-primary text-white hover:bg-primary/90 transition-all flex items-center gap-1 shadow-xs cursor-pointer active:scale-95"
                  title="Tampilkan kurva langkah ini pada grafik trend di bawah"
                >
                  📈 Tampilkan Kurva
                </button>
                <button
                  onClick={() => setSelectedStepDetail(null)}
                  className="w-7 h-7 bg-rose-600 hover:bg-rose-700 active:scale-95 text-white font-bold rounded-lg flex items-center justify-center shadow-sm transition-all cursor-pointer shrink-0"
                  title="Tutup Popup"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Scrollable Modal Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
              {/* Comment / Remark (Slot 0) from PRG Recipe */}
              {selectedStepDetail.comment && (
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 flex items-center justify-between text-xs text-blue-950 dark:text-blue-100 shadow-2xs">
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg">📝</span>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-blue-600 dark:text-blue-400 tracking-wider">
                        Catatan / Komentar Resep (Slot 0):
                      </div>
                      <div className="font-mono font-extrabold text-sm text-blue-950 dark:text-blue-100 mt-0.5">
                        {selectedStepDetail.comment}
                      </div>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-300 font-bold border border-blue-300 dark:border-blue-700">
                    INSTRUCTION REMARK
                  </span>
                </div>
              )}

              {/* Operator Intervention Alert */}
              {selectedStepDetail.has_intervention && !String(selectedStepDetail.actual_p1 || '').includes('76.8') && (
                <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700/60 flex items-center justify-between text-xs text-amber-900 dark:text-amber-200 shadow-xs animate-in fade-in">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">⚠️</span>
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

              {/* Recipe Targets & Timings 6-Grid */}
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-meta-4/40 border border-stroke dark:border-strokedark grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-center text-xs font-mono">
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Target Resep (Set)</div>
                  <div className="font-bold text-black dark:text-white mt-0.5">
                    {selectedStepDetail.set_time ? `${selectedStepDetail.set_time} min` : (selectedStepDetail.target_min ? `${selectedStepDetail.target_min} min` : 'Variabel')}
                  </div>
                </div>
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Waktu Tahan (Hold)</div>
                  <div className="font-bold text-black dark:text-white mt-0.5">
                    {selectedStepDetail.hold_time ? `${selectedStepDetail.hold_time} min` : '-'}
                  </div>
                </div>
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Proteksi (Max)</div>
                  <div className="font-bold text-black dark:text-white mt-0.5">
                    {selectedStepDetail.protect_time ? `${selectedStepDetail.protect_time} min` : '-'}
                  </div>
                </div>
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Waktu Mulai</div>
                  <div className="font-bold text-black dark:text-white mt-0.5">
                    {selectedStepDetail.start_time ? formatStepTime(selectedStepDetail.start_time) : '-'}
                  </div>
                </div>
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Waktu Selesai</div>
                  <div className="font-bold text-black dark:text-white mt-0.5">
                    {selectedStepDetail.no === currentStepNo ? (
                      <span className="text-primary font-bold animate-pulse">Sedang Berjalan</span>
                    ) : (
                      selectedStepDetail.end_time ? formatStepTime(selectedStepDetail.end_time) : '-'
                    )}
                  </div>
                </div>
                <div className="p-1.5 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Durasi & Deviasi</div>
                  <div className="mt-0.5 flex flex-col items-center">
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">
                      {selectedStepDetail.no === currentStepNo
                        ? `${getElapsedDuration(selectedStepDetail.start_time) || selectedStepDetail.duration_text || 'Berjalan...'}`
                        : (selectedStepDetail.duration_text || '-')}
                    </span>
                    {(() => {
                      const liveRem = selectedStepDetail.no === currentStepNo
                        ? getLiveRemainingText(selectedStepDetail.start_time, selectedStepDetail.target_min || selectedStepDetail.set_time)
                        : null;
                      const text = liveRem?.text || selectedStepDetail.delta_text;
                      const isOver = liveRem ? liveRem.isOvertime : (selectedStepDetail.time_status === 'SLOWER' || selectedStepDetail.time_status === 'OVERTIME');
                      if (!text) return null;
                      return (
                        <span className={`text-[9px] font-bold px-1 rounded mt-0.5 ${
                          isOver
                            ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30'
                            : (selectedStepDetail.time_status === 'FASTER'
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                              : 'text-gray-500')
                        }`}>
                          {text}
                        </span>
                      );
                    })()}
                  </div>
                </div>
              </div>

              {/* Comprehensive Sub-Steps & Parameter Table */}
              <div className="border border-stroke dark:border-strokedark rounded-lg overflow-hidden shadow-2xs">
                <table className="w-full text-xs text-left">
                  <thead className="bg-gray-100 dark:bg-meta-4 text-body dark:text-bodydark uppercase font-bold border-b border-stroke dark:border-strokedark font-mono">
                    <tr>
                      <th className="py-2.5 px-3 w-16 text-center border-r border-stroke dark:border-strokedark">Slot</th>
                      <th className="py-2.5 px-3 w-48 border-r border-stroke dark:border-strokedark">Fungsi / Resource</th>
                      <th className="py-2.5 px-3 border-r border-stroke dark:border-strokedark">Parameter Lengkap Resep (P1 - P6)</th>
                      <th className="py-2.5 px-3 w-36 text-center">Aktual / Δ</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stroke dark:divide-strokedark font-sans">
                    {(selectedStepDetail.sub_steps && selectedStepDetail.sub_steps.length > 0
                      ? selectedStepDetail.sub_steps
                      : [{ line: 1, name: selectedStepDetail.name, params: selectedStepDetail.params, p1: selectedStepDetail.p1, p2: selectedStepDetail.p2, p3: selectedStepDetail.p3, is_sub: false }]
                    ).map((line, idx) => {
                      const isMain = !line.is_sub && line.line === 1;
                      const activeParams = line.params && line.params.length > 0
                        ? line.params.filter(p => p.formatted && p.formatted !== '0' && p.formatted !== '0.0' && p.formatted !== 'Off')
                        : [
                            line.p1 ? { pos: 1, name: 'P1', formatted: line.p1 } : null,
                            line.p2 ? { pos: 2, name: 'P2', formatted: line.p2 } : null,
                            line.p3 ? { pos: 3, name: 'P3', formatted: line.p3 } : null,
                            line.p4 ? { pos: 4, name: 'P4', formatted: line.p4 } : null
                          ].filter(Boolean);

                      return (
                        <tr
                          key={idx}
                          className={`${isMain
                            ? 'bg-primary/5 dark:bg-primary/10 font-medium'
                            : idx % 2 === 0
                              ? 'bg-white dark:bg-boxdark text-black dark:text-white'
                              : 'bg-gray dark:bg-meta-4/20 text-black dark:text-white'
                            } transition-colors`}
                        >
                          <td className={`py-2.5 px-3 text-center font-mono border-r ${isMain ? 'font-extrabold text-primary text-sm' : 'border-stroke dark:border-strokedark text-gray-400'}`}>
                            {String(line.line).padStart(2, '0')}
                          </td>
                          <td className={`py-2.5 px-3 border-r border-stroke dark:border-strokedark`}>
                            <div className="font-bold text-black dark:text-white flex items-center gap-1.5">
                              {line.func_name || line.name}
                              {line.func_id > 0 && (
                                <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-gray-200 dark:bg-meta-4 text-gray-700 dark:text-gray-300">
                                  F{line.func_id}
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-gray-500 font-mono mt-0.5">
                              {line.resource_name || (isMain ? 'Main Process Kier' : `Resource Slot ${line.line}`)}
                            </div>
                          </td>
                          <td className={`py-2.5 px-3 border-r border-stroke dark:border-strokedark`}>
                            {activeParams.length > 0 ? (
                              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-1.5">
                                {activeParams.map((p, pi) => (
                                  <div
                                    key={pi}
                                    className="flex items-center justify-between px-2 py-1 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-[11px] font-mono shadow-2xs hover:border-primary/40 transition-colors"
                                    title={`${p.name}: ${p.formatted}`}
                                  >
                                    <span className="text-gray-500 truncate mr-1.5 max-w-[110px]" title={p.name}>{p.name}:</span>
                                    <span className="font-bold text-black dark:text-white shrink-0">{p.formatted}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <span className="text-gray-400 text-[11px] italic">Tidak ada parameter numerik</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono">
                            {line.has_delta && !String(line.actual_p1 || '').includes('76.8') ? (
                              <span className="inline-block px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 font-bold font-mono text-[11px] border border-amber-300 dark:border-amber-700">
                                {line.actual_p1} (Δ {line.delta_p1})
                              </span>
                            ) : isMain && selectedStepDetail.telemetry?.pv_end ? (
                              <div className="text-emerald-600 dark:text-emerald-400 font-mono font-bold text-[11px]">
                                PV: {selectedStepDetail.telemetry.pv_end} °C
                              </div>
                            ) : (line.func_id === 404 || line.name?.toLowerCase().includes('pump')) && selectedStepDetail.telemetry?.pump_avg ? (
                              <div className="text-emerald-600 dark:text-emerald-400 font-mono font-bold text-[11px]" title="Rata-rata kecepatan pompa aktual">
                                Pompa: {selectedStepDetail.telemetry.pump_avg} %
                              </div>
                            ) : (line.func_id === 712 || line.func_id === 411 || line.name?.toLowerCase().includes('flow') || line.name?.toLowerCase().includes('reel')) && selectedStepDetail.telemetry?.reel_avg ? (
                              <div className="text-emerald-600 dark:text-emerald-400 font-mono font-bold text-[11px]" title="Rata-rata kecepatan reel kain aktual">
                                Reel: {selectedStepDetail.telemetry.reel_avg} m/min
                              </div>
                            ) : isMain ? (
                              <span className="text-emerald-600 dark:text-emerald-400 text-[11px] font-medium">Sesuai Resep</span>
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

              {/* Physical Sensor Telemetry Snapshot During This Step */}
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-meta-4/30 border border-stroke dark:border-strokedark">
                <div className="text-[11px] font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 flex-wrap">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                    Pembacaan Telemetri Sensor Aktual Pada Langkah Ini
                    {liveData?.iw_source && selectedStepDetail.no === currentStepNo && (
                      <span className="ml-1 text-[9px] font-bold text-emerald-600 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                        ⚡ Real-Time IW (Object 1025)
                      </span>
                    )}
                  </span>
                  {selectedStepDetail.telemetry?.point_count ? (
                    <span className="text-[10px] text-gray-500 font-mono bg-white dark:bg-boxdark px-1.5 py-0.5 rounded border border-stroke dark:border-strokedark">
                      {selectedStepDetail.telemetry.point_count} Titik Telemetri
                    </span>
                  ) : (
                    <span className="text-[10px] text-gray-400 font-mono">
                      {selectedStepDetail.no === currentStepNo ? 'Sensor Real-Time' : 'Data Arsip'}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs font-mono">
                  <div className="p-2 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark shadow-2xs">
                    <div className="text-[10px] text-gray-500 uppercase font-semibold">Suhu Bejana T1 (PV)</div>
                    <div className="font-extrabold text-black dark:text-white text-sm mt-0.5">
                      {selectedStepDetail.telemetry?.pv_end !== undefined && selectedStepDetail.telemetry?.pv_end !== null
                        ? `${selectedStepDetail.telemetry.pv_end} °C`
                        : (selectedStepDetail.no === currentStepNo && liveData?.current_temp !== undefined
                          ? `${liveData.current_temp} °C`
                          : '-')}
                    </div>
                    {selectedStepDetail.telemetry?.pv_avg ? (
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        Avg: {selectedStepDetail.telemetry.pv_avg} °C (Min: {selectedStepDetail.telemetry.pv_min} - Max: {selectedStepDetail.telemetry.pv_max})
                      </div>
                    ) : (
                      <div className="text-[10px] text-gray-400 mt-0.5">Sensor Utama T1</div>
                    )}
                  </div>

                  <div className="p-2 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark shadow-2xs">
                    <div className="text-[10px] text-gray-500 uppercase font-semibold">Setpoint (SP)</div>
                    <div className={`font-extrabold text-sm mt-0.5 ${isStepWithTempSetpoint(selectedStepDetail) ? 'text-primary dark:text-secondary' : 'text-gray-400 dark:text-gray-500'}`}>
                      {(() => {
                        if (!isStepWithTempSetpoint(selectedStepDetail)) {
                          return '-';
                        }
                        const stTarget = getStepTargetTemp(selectedStepDetail);
                        if (stTarget !== null && stTarget > 0) {
                          return `${stTarget} °C`;
                        }
                        if (selectedStepDetail.telemetry?.sp !== undefined && selectedStepDetail.telemetry?.sp !== null && selectedStepDetail.telemetry.sp > 0 && Math.abs(selectedStepDetail.telemetry.sp - 90.0) > 0.1 && Math.abs(selectedStepDetail.telemetry.sp - 76.8) > 0.1) {
                          return `${selectedStepDetail.telemetry.sp} °C`;
                        }
                        if (selectedStepDetail.p1?.includes('°C')) {
                          return selectedStepDetail.p1;
                        }
                        if (selectedStepDetail.no === currentStepNo && liveData?.curve?.slice(-1)[0]?.temp_sp !== undefined && liveData.curve.slice(-1)[0].temp_sp > 0 && Math.abs(liveData.curve.slice(-1)[0].temp_sp - 90.0) > 0.1 && Math.abs(liveData.curve.slice(-1)[0].temp_sp - 76.8) > 0.1) {
                          return `${liveData.curve.slice(-1)[0].temp_sp} °C`;
                        }
                        return '-';
                      })()}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">
                      {isStepWithTempSetpoint(selectedStepDetail) ? 'Target Suhu' : 'Tanpa Target Suhu'}
                    </div>
                  </div>

                  <div className="p-2 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark shadow-2xs">
                    <div className="text-[10px] text-gray-500 uppercase font-semibold">Pompa Sirkulasi</div>
                    <div className="font-extrabold text-black dark:text-white text-sm mt-0.5">
                      {selectedStepDetail.telemetry?.pump_avg !== undefined && selectedStepDetail.telemetry?.pump_avg !== null
                        ? `${selectedStepDetail.telemetry.pump_avg} %`
                        : (selectedStepDetail.no === currentStepNo && liveData?.curve?.slice(-1)[0]?.pump_speed_percent !== undefined
                          ? `${liveData.curve.slice(-1)[0].pump_speed_percent} %`
                          : (selectedStepDetail.sub_steps?.find(s => s.func_id === 404)?.p2 || '-'))}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">Kecepatan Pompa</div>
                  </div>

                  <div className="p-2 rounded bg-white dark:bg-boxdark border border-stroke dark:border-strokedark shadow-2xs">
                    <div className="text-[10px] text-gray-500 uppercase font-semibold">Material Flow (Reel)</div>
                    <div className="font-extrabold text-black dark:text-white text-sm mt-0.5">
                      {selectedStepDetail.telemetry?.reel_avg !== undefined && selectedStepDetail.telemetry?.reel_avg !== null
                        ? `${selectedStepDetail.telemetry.reel_avg} m/min`
                        : (selectedStepDetail.no === currentStepNo && liveData?.curve?.slice(-1)[0]?.reel_speed_mpm !== undefined
                          ? `${liveData.curve.slice(-1)[0].reel_speed_mpm} m/min`
                          : (selectedStepDetail.sub_steps?.find(s => s.func_id === 712 || s.func_id === 411)?.p2 || '-'))}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">Kecepatan Kain</div>
                  </div>
                </div>
              </div>

              {/* Step-specific Alarms / Events if occurred */}
              {selectedStepDetail.alarms && selectedStepDetail.alarms.length > 0 && (
                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 text-xs">
                  <div className="font-bold text-rose-700 dark:text-rose-300 mb-1 flex items-center gap-1.5">
                    <span>🚨</span> Alarm / Event Terdeteksi Selama Langkah Ini ({selectedStepDetail.alarms.length}):
                  </div>
                  <div className="space-y-1">
                    {selectedStepDetail.alarms.map((a, ai) => (
                      <div key={ai} className="flex items-center justify-between font-mono text-[11px] text-rose-900 dark:text-rose-200">
                        <span>[{a.alarm_code}] {a.alarm_text}</span>
                        <span className="text-gray-500">{a.timestamp}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer with Step Navigator */}
            <div className="bg-gray-50 dark:bg-meta-4 px-4 py-3 border-t border-stroke dark:border-strokedark flex items-center justify-between shrink-0">
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
      {/* ========================================================================= */}
      {/* MODAL SETEX MULTI-OBJECT & LIVE REGISTER INSPECTOR VIA TCP PORT 50000 */}
      {/* ========================================================================= */}
      {showIwModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="SETEX Live Multi-Object & Register Inspector"
          onClick={() => setShowIwModal(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fadeIn"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-boxdark rounded-xl shadow-2xl max-w-5xl w-full border border-stroke dark:border-strokedark overflow-hidden flex flex-col max-h-[92vh]"
          >
            {/* Header */}
            <div className="bg-gray-100 dark:bg-meta-4 px-5 py-4 border-b border-stroke dark:border-strokedark flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-black dark:text-white flex items-center gap-2">
                    SETEX Controller - Live Multi-Object & Register Inspector
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500 text-white">
                      TCP :50000
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-primary/20 text-primary border border-primary/30">
                      Multi-Object (1025, 1009, 1010, 6, 1035)
                    </span>
                  </h3>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">
                    Streaming real-time multi-objek dari Kontroler Mesin {selectedMachine} ({hmiIp}:50000)
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={fetchIwRegisters}
                  disabled={iwLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded bg-primary text-white hover:bg-primary/90 transition-all cursor-pointer shadow-xs disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${iwLoading ? 'animate-spin' : ''}`} />
                  Segarkan Data
                </button>
                <button
                  onClick={() => setShowIwModal(false)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-danger hover:bg-gray-200 dark:hover:bg-meta-4 transition-colors cursor-pointer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4">
              {(() => {
                const currentIw = iwDetail || liveData?.iw_telemetry;
                const objects = currentIw?.objects || {};
                const summary = currentIw?.summary || {};

                // Values extraction
                const tempPv = summary.act_temp_pv ?? currentIw?.iw_t1_pv ?? (currentIw?.raw_words?.[0] ? (currentIw.raw_words[0] / 100).toFixed(2) : null);
                const tempSv = summary.set_temp_sv ?? (objects.SET_1009?.registers?.find(r => r.address === 3 || r.address === 1)?.calibrated_value ?? null);
                const gradSv = summary.gradient_sv ?? null;
                const holdSv = summary.holding_time_sv ?? null;

                const pumpPv = summary.act_pump_pv ?? currentIw?.iw_pump_act ?? (currentIw?.raw_words?.[20] !== undefined ? currentIw.raw_words[20] : null);
                const pumpSv = summary.set_pump_sp ?? currentIw?.iw_pump_sp ?? (objects.SET_1009?.registers?.find(r => r.address === 5)?.calibrated_value ?? null);

                const levelPv = currentIw?.iw_level_act ?? (currentIw?.raw_words?.[11] !== undefined ? currentIw.raw_words[11] : null);
                const fillSv = summary.fill_quantity_sv_l ?? (objects.SET_1009?.registers?.find(r => r.address === 9)?.calibrated_value ?? null);
                const waterMeter = currentIw?.iw_water_counter ?? currentIw?.raw_words?.[12] ?? currentIw?.raw_words?.[14] ?? null;

                const reelPv = summary.reel_act ?? currentIw?.iw_reel_act ?? (currentIw?.raw_words?.[21] !== undefined ? currentIw.raw_words[21] : null);

                // Object registers
                const iwObj = objects.IW_1025 || {};
                const setObj = objects.SET_1009 || {};
                const actObj = objects.ACT_1010 || {};
                const funcObj = objects.FUNCTION_6 || {};
                const batchObj = objects.BATCH_1035 || {};

                // Decoded IW rows
                const decodedIwList = iwObj.registers || currentIw?.decoded_registers || [];
                const rawWords = currentIw?.raw_words || [];

                let iwRows = [];
                if (decodedIwList.length > 0) {
                  for (const reg of decodedIwList) {
                    const isNonZero = reg.raw_val !== 0;
                    const isKey = [1, 2, 10, 11, 12, 13, 15, 16, 21, 22, 25, 27, 28, 30, 34].includes(reg.index || reg.address);
                    if (iwShowAllRegisters || isNonZero || isKey) {
                      iwRows.push({
                        num: reg.index || reg.address,
                        val: reg.raw_val ?? reg.raw,
                        hex: reg.hex || `0x${((reg.raw_val ?? reg.raw) || 0).toString(16).toUpperCase().padStart(4, '0')}`,
                        name: reg.name,
                        converted: reg.formatted || `${reg.conv_val ?? reg.calibrated_value} ${reg.unit || ''}`.trim(),
                        isNonZero
                      });
                    }
                  }
                } else if (rawWords.length > 0) {
                  const IW_DESCRIPTIONS = {
                    1: { name: 'act.Temp.', conv: (v) => `${(v * 150 / 10000).toFixed(2)} °C` },
                    2: { name: 'Time', conv: (v) => `${v} min` },
                    10: { name: 'Set temperature', conv: (v) => `${(v * 100 / 6666).toFixed(1)} °C` },
                    11: { name: 'level machine dig.', conv: (v) => `${v}` },
                    12: { name: 'level machine (%)', conv: (v) => `${v} %` },
                    13: { name: 'quantity machine (L)', conv: (v) => `${v} L` },
                    15: { name: 'water counter IW', conv: (v) => `${v} L` },
                    16: { name: 'pressure machine', conv: (v) => `${v} bar` },
                    21: { name: 'speed main pump', conv: (v) => `${v} %` },
                    22: { name: 'winch speed', conv: (v) => `${v} m/min` },
                    25: { name: 'Temperature ST', conv: (v) => `${(v * 150 / 10000).toFixed(2)} °C` },
                    27: { name: 'level ST [L]', conv: (v) => `${v} L` },
                    28: { name: 'level ST (%)', conv: (v) => `${v} %` },
                    30: { name: 'Temperature AT', conv: (v) => `${(v * 150 / 10000).toFixed(2)} °C` },
                    34: { name: 'start dosing amo AT2', conv: (v) => `${(v / 10).toFixed(1)} L` }
                  };
                  for (let idx = 0; idx < rawWords.length; idx++) {
                    const num = idx + 1;
                    const val = rawWords[idx];
                    const meta = IW_DESCRIPTIONS[num];
                    if (iwShowAllRegisters || val !== 0 || meta) {
                      iwRows.push({
                        num,
                        val,
                        hex: `0x${val.toString(16).toUpperCase().padStart(4, '0')}`,
                        name: meta?.name || `Info Word Channel ${num}`,
                        converted: meta?.conv ? meta.conv(val) : String(val),
                        isNonZero: val !== 0
                      });
                    }
                  }
                }

                // Filter search
                if (iwSearchFilter.trim()) {
                  const s = iwSearchFilter.toLowerCase().trim();
                  iwRows = iwRows.filter(r => 
                    `iw ${r.num}`.includes(s) || 
                    String(r.name).toLowerCase().includes(s) || 
                    String(r.converted).toLowerCase().includes(s) || 
                    String(r.hex).toLowerCase().includes(s)
                  );
                }

                // SET rows
                let setRows = setObj.registers || [];
                if (iwSearchFilter.trim()) {
                  const s = iwSearchFilter.toLowerCase().trim();
                  setRows = setRows.filter(r => 
                    `set ${r.address}`.includes(s) || 
                    String(r.name).toLowerCase().includes(s) || 
                    String(r.name_local || '').toLowerCase().includes(s)
                  );
                }

                // ACT rows
                let actRows = actObj.registers || [];
                if (iwSearchFilter.trim()) {
                  const s = iwSearchFilter.toLowerCase().trim();
                  actRows = actRows.filter(r => 
                    `act ${r.address}`.includes(s) || 
                    String(r.hex).toLowerCase().includes(s)
                  );
                }

                // BATCH counters
                const batchCounters = batchObj.counters || [];

                return (
                  <>
                    {/* Top KPI Cards (Multi-Object Overview) */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {/* Suhu Bejana PV vs SV */}
                      <div className="p-3.5 rounded-lg bg-emerald-50/50 dark:bg-meta-4 border border-emerald-200 dark:border-strokedark shadow-2xs">
                        <div className="text-[11px] font-bold text-gray-500 uppercase flex items-center justify-between">
                          <span>Suhu Bejana (PV / SV)</span>
                          <Flame className="h-4 w-4 text-rose-500" />
                        </div>
                        <div className="flex items-baseline gap-2 mt-1">
                          <span className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400">
                            {tempPv !== null ? `${tempPv} °C` : '-'}
                          </span>
                          {tempSv !== null && (
                            <span className="text-xs font-mono font-bold text-gray-500 bg-gray-200 dark:bg-boxdark px-1.5 py-0.5 rounded">
                              Target: {tempSv} °C
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono mt-1">
                          {gradSv ? `Gradien: ${gradSv} °C/min | ` : ''}
                          {holdSv ? `Tahan: ${holdSv} min` : 'Objek 1025 IW 1 & Objek 6'}
                        </div>
                      </div>

                      {/* Pompa Sirkulasi PV vs SV */}
                      <div className="p-3.5 rounded-lg bg-white dark:bg-meta-4 border border-stroke dark:border-strokedark shadow-2xs">
                        <div className="text-[11px] font-bold text-gray-500 uppercase flex items-center justify-between">
                          <span>Pompa Sirkulasi (PV / SV)</span>
                          <Gauge className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex items-baseline gap-2 mt-1">
                          <span className="text-2xl font-black font-mono text-primary">
                            {pumpPv !== null ? `${pumpPv} %` : '-'}
                          </span>
                          {pumpSv !== null && (
                            <span className="text-xs font-mono font-bold text-gray-500 bg-gray-200 dark:bg-boxdark px-1.5 py-0.5 rounded">
                              Target: {pumpSv} %
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono mt-1">
                          Kecepatan Sirkulasi Main Kier (IW 21 & SET)
                        </div>
                      </div>

                      {/* Level & Pengisian Bejana */}
                      <div className="p-3.5 rounded-lg bg-white dark:bg-meta-4 border border-stroke dark:border-strokedark shadow-2xs">
                        <div className="text-[11px] font-bold text-gray-500 uppercase flex items-center justify-between">
                          <span>Level & Meter Air</span>
                          <Clock className="h-4 w-4 text-meta-5" />
                        </div>
                        <div className="flex items-baseline gap-2 mt-1">
                          <span className="text-2xl font-black font-mono text-black dark:text-white">
                            {levelPv !== null ? `${levelPv} %` : '-'}
                          </span>
                          {fillSv !== null && (
                            <span className="text-xs font-mono font-bold text-gray-500 bg-gray-200 dark:bg-boxdark px-1.5 py-0.5 rounded">
                              Isi: {fillSv} L
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono mt-1">
                          {waterMeter !== null ? `Total Meter: ${waterMeter} L` : 'Level Mesin (IW 12 & IW 13)'}
                        </div>
                      </div>

                      {/* Material Flow / Winch */}
                      <div className="p-3.5 rounded-lg bg-white dark:bg-meta-4 border border-stroke dark:border-strokedark shadow-2xs">
                        <div className="text-[11px] font-bold text-gray-500 uppercase flex items-center justify-between">
                          <span>Material Flow / Winch</span>
                          <Activity className="h-4 w-4 text-emerald-500" />
                        </div>
                        <div className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                          {reelPv !== null ? `${reelPv} m/min` : '-'}
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono mt-1">
                          Kecepatan Putaran Kain (IW 22)
                        </div>
                      </div>
                    </div>

                    {/* Navigation Tabs Multi-Object */}
                    <div className="border-b border-stroke dark:border-strokedark flex items-center justify-between pt-1">
                      <div className="flex items-center gap-1 overflow-x-auto">
                        <button
                          onClick={() => setIwActiveTab('1025_iw')}
                          className={`px-3.5 py-2 text-xs font-bold rounded-t-lg transition-all flex items-center gap-1.5 border-b-2 cursor-pointer ${
                            iwActiveTab === '1025_iw'
                              ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-50/50 dark:bg-meta-4'
                              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Activity className="h-3.5 w-3.5" />
                          <span>Objek 1025: IW (Sensor PV)</span>
                          <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                            {Object.keys(currentIw?.non_zero || {}).length || iwRows.filter(r => r.isNonZero).length}
                          </span>
                        </button>

                        <button
                          onClick={() => setIwActiveTab('1009_set')}
                          className={`px-3.5 py-2 text-xs font-bold rounded-t-lg transition-all flex items-center gap-1.5 border-b-2 cursor-pointer ${
                            iwActiveTab === '1009_set'
                              ? 'border-primary text-primary bg-primary/10'
                              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Sliders className="h-3.5 w-3.5" />
                          <span>Objek 1009: SET (Target / SOLL)</span>
                          <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-primary/15 text-primary">
                            {setRows.length}
                          </span>
                        </button>

                        <button
                          onClick={() => setIwActiveTab('1010_act')}
                          className={`px-3.5 py-2 text-xs font-bold rounded-t-lg transition-all flex items-center gap-1.5 border-b-2 cursor-pointer ${
                            iwActiveTab === '1010_act'
                              ? 'border-meta-5 text-meta-5 bg-meta-5/10'
                              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Gauge className="h-3.5 w-3.5" />
                          <span>Objek 1010: ACT (Feedback Loop)</span>
                          <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-meta-5/15 text-meta-5">
                            {actRows.length}
                          </span>
                        </button>

                        <button
                          onClick={() => setIwActiveTab('6_func')}
                          className={`px-3.5 py-2 text-xs font-bold rounded-t-lg transition-all flex items-center gap-1.5 border-b-2 cursor-pointer ${
                            iwActiveTab === '6_func'
                              ? 'border-rose-500 text-rose-500 bg-rose-500/10'
                              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Layers className="h-3.5 w-3.5" />
                          <span>Objek 6: Resep Aktif (Function)</span>
                          <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-rose-500/15 text-rose-500">
                            {Object.keys(funcObj.functions || {}).length}
                          </span>
                        </button>

                        <button
                          onClick={() => setIwActiveTab('1035_batch')}
                          className={`px-3.5 py-2 text-xs font-bold rounded-t-lg transition-all flex items-center gap-1.5 border-b-2 cursor-pointer ${
                            iwActiveTab === '1035_batch'
                              ? 'border-amber-500 text-amber-500 bg-amber-500/10'
                              : 'border-transparent text-gray-500 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Database className="h-3.5 w-3.5" />
                          <span>Objek 1035: Konsumsi Batch</span>
                          <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-amber-500/15 text-amber-500">
                            {batchCounters.length}
                          </span>
                        </button>
                      </div>

                      {/* Filter Search */}
                      <div className="flex items-center gap-2 pb-1">
                        <div className="relative">
                          <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                          <input
                            type="text"
                            placeholder="Cari parameter / sinyal..."
                            value={iwSearchFilter}
                            onChange={(e) => setIwSearchFilter(e.target.value)}
                            className="pl-8 pr-2.5 py-1 text-xs rounded border border-stroke dark:border-strokedark bg-white dark:bg-boxdark text-black dark:text-white w-48 focus:outline-none focus:border-primary"
                          />
                        </div>
                        {iwActiveTab === '1025_iw' && (
                          <button
                            onClick={() => setIwShowAllRegisters(!iwShowAllRegisters)}
                            className={`px-2.5 py-1 text-[11px] font-bold rounded border transition-colors cursor-pointer ${
                              iwShowAllRegisters
                                ? 'bg-primary text-white border-primary'
                                : 'bg-gray-100 dark:bg-meta-4 text-gray-600 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-200'
                            }`}
                            title="Beralih antara menampilkan semua register terkonfigurasi (1..200) atau hanya register yang sedang aktif / non-zero"
                          >
                            {iwShowAllRegisters ? 'Tampil: Semua (1..200)' : 'Tampil: Aktif Saja'}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* ======================================================= */}
                    {/* TAB 1: OBJEK 1025 - INFO WORDS (SENSOR PROCESS VALUES) */}
                    {/* ======================================================= */}
                    {iwActiveTab === '1025_iw' && (
                      <div className="border border-stroke dark:border-strokedark rounded-lg overflow-hidden">
                        <div className="bg-gray-50 dark:bg-meta-4 px-4 py-2 border-b border-stroke dark:border-strokedark flex items-center justify-between">
                          <span className="text-xs font-bold text-black dark:text-white">
                            Daftar Register IW Telemetri Sensor Proses ({iwRows.length} Register Ditampilkan, {currentIw?.word_count || 80} Word Dibaca):
                          </span>
                          <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                            Protokol SC737 Svc 11 / Objek 1025
                          </span>
                        </div>

                        <table className="w-full text-xs text-left">
                          <thead className="bg-gray-100 dark:bg-boxdark text-gray-500 uppercase font-mono text-[10px] border-b border-stroke dark:border-strokedark">
                            <tr>
                              <th className="py-2 px-3 w-24">Register</th>
                              <th className="py-2 px-3">Nama Sinyal / Parameter PLC</th>
                              <th className="py-2 px-3 w-28 text-right">Nilai Mentah</th>
                              <th className="py-2 px-3 w-24 text-right">Hex</th>
                              <th className="py-2 px-3 w-36 text-right">Nilai Terkonversi</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-stroke dark:divide-strokedark font-mono">
                            {iwRows.length === 0 ? (
                              <tr>
                                <td colSpan={5} className="py-6 text-center text-gray-400 italic">
                                  {iwLoading ? 'Sedang membaca data register IW...' : 'Tidak ada register IW yang cocok dengan filter'}
                                </td>
                              </tr>
                            ) : (
                              iwRows.map((r, i) => (
                                <tr key={r.num} className={i % 2 === 0 ? 'bg-white dark:bg-boxdark' : 'bg-gray-50/50 dark:bg-meta-4/20'}>
                                  <td className="py-2 px-3 font-bold text-primary">IW {r.num}</td>
                                  <td className="py-2 px-3 font-sans text-black dark:text-white font-medium">{r.name}</td>
                                  <td className="py-2 px-3 text-right font-bold text-black dark:text-white">{r.val}</td>
                                  <td className="py-2 px-3 text-right text-gray-400 text-[11px]">{r.hex}</td>
                                  <td className={`py-2 px-3 text-right font-bold ${r.isNonZero ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400'}`}>
                                    {r.converted}
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* ======================================================= */}
                    {/* TAB 2: OBJEK 1009 - SET (TARGET SETPOINTS / SOLL)       */}
                    {/* ======================================================= */}
                    {iwActiveTab === '1009_set' && (
                      <div className="border border-stroke dark:border-strokedark rounded-lg overflow-hidden">
                        <div className="bg-gray-50 dark:bg-meta-4 px-4 py-2 border-b border-stroke dark:border-strokedark flex items-center justify-between">
                          <span className="text-xs font-bold text-black dark:text-white">
                            Parameter Target / Setpoint Resep Kontroler ({setRows.length} Parameter):
                          </span>
                          <span className="text-[10px] font-mono text-primary font-bold">
                            Protokol SC737 Svc 11 / Objek 1009 (SET)
                          </span>
                        </div>

                        <table className="w-full text-xs text-left">
                          <thead className="bg-gray-100 dark:bg-boxdark text-gray-500 uppercase font-mono text-[10px] border-b border-stroke dark:border-strokedark">
                            <tr>
                              <th className="py-2 px-3 w-28">Alamat SET</th>
                              <th className="py-2 px-3">Nama Parameter PLC</th>
                              <th className="py-2 px-3">Deskripsi / Lokal</th>
                              <th className="py-2 px-3 w-28 text-right">Nilai Mentah</th>
                              <th className="py-2 px-3 w-24 text-right">Hex</th>
                              <th className="py-2 px-3 w-36 text-right">Nilai Target (SV)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-stroke dark:divide-strokedark font-mono">
                            {setRows.length === 0 ? (
                              <tr>
                                <td colSpan={6} className="py-6 text-center text-gray-400 italic">
                                  {iwLoading ? 'Sedang membaca parameter setpoint...' : 'Belum ada parameter SET yang terbaca'}
                                </td>
                              </tr>
                            ) : (
                              setRows.map((r, i) => (
                                <tr key={r.address} className={i % 2 === 0 ? 'bg-white dark:bg-boxdark' : 'bg-gray-50/50 dark:bg-meta-4/20'}>
                                  <td className="py-2 px-3 font-bold text-primary">SET {r.address}</td>
                                  <td className="py-2 px-3 font-sans text-black dark:text-white font-medium">{r.name}</td>
                                  <td className="py-2 px-3 font-sans text-gray-500 text-[11px]">{r.name_local || '-'}</td>
                                  <td className="py-2 px-3 text-right font-bold text-black dark:text-white">{r.raw}</td>
                                  <td className="py-2 px-3 text-right text-gray-400 text-[11px]">{r.hex}</td>
                                  <td className="py-2 px-3 text-right font-bold text-primary">
                                    {r.formatted || `${r.calibrated_value} ${r.unit || ''}`.trim()}
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* ======================================================= */}
                    {/* TAB 3: OBJEK 1010 - ACT (LOOP FEEDBACK / IST)          */}
                    {/* ======================================================= */}
                    {iwActiveTab === '1010_act' && (
                      <div className="border border-stroke dark:border-strokedark rounded-lg overflow-hidden">
                        <div className="bg-gray-50 dark:bg-meta-4 px-4 py-2 border-b border-stroke dark:border-strokedark flex items-center justify-between">
                          <span className="text-xs font-bold text-black dark:text-white">
                            Feedback Loop Aktual Kontroler ({actRows.length} Register Aktif):
                          </span>
                          <span className="text-[10px] font-mono text-meta-5 font-bold">
                            Protokol SC737 Svc 11 / Objek 1010 (ACT)
                          </span>
                        </div>

                        <table className="w-full text-xs text-left">
                          <thead className="bg-gray-100 dark:bg-boxdark text-gray-500 uppercase font-mono text-[10px] border-b border-stroke dark:border-strokedark">
                            <tr>
                              <th className="py-2 px-3 w-28">Alamat ACT</th>
                              <th className="py-2 px-3">Nama Sinyal</th>
                              <th className="py-2 px-3 w-32 text-right">Nilai Mentah</th>
                              <th className="py-2 px-3 w-28 text-right">Hex</th>
                              <th className="py-2 px-3 w-28 text-right">Peran</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-stroke dark:divide-strokedark font-mono">
                            {actRows.length === 0 ? (
                              <tr>
                                <td colSpan={5} className="py-6 text-center text-gray-400 italic">
                                  {iwLoading ? 'Sedang membaca feedback loop ACT...' : 'Belum ada register ACT terbaca'}
                                </td>
                              </tr>
                            ) : (
                              actRows.map((r, i) => (
                                <tr key={r.address} className={i % 2 === 0 ? 'bg-white dark:bg-boxdark' : 'bg-gray-50/50 dark:bg-meta-4/20'}>
                                  <td className="py-2 px-3 font-bold text-meta-5">ACT {r.address}</td>
                                  <td className="py-2 px-3 font-sans text-black dark:text-white font-medium">{r.name}</td>
                                  <td className="py-2 px-3 text-right font-bold text-black dark:text-white">{r.raw}</td>
                                  <td className="py-2 px-3 text-right text-gray-400 text-[11px]">{r.hex}</td>
                                  <td className="py-2 px-3 text-right text-gray-500 text-[11px] font-bold">{r.role || 'PV'}</td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* ======================================================= */}
                    {/* TAB 4: OBJEK 6 - RESEP LANGKAH AKTIF (FUNCTION 141/713) */}
                    {/* ======================================================= */}
                    {iwActiveTab === '6_func' && (
                      <div className="space-y-3">
                        <div className="bg-gray-50 dark:bg-meta-4 px-4 py-2 border border-stroke dark:border-strokedark rounded-lg flex items-center justify-between">
                          <span className="text-xs font-bold text-black dark:text-white">
                            Resep Langkah Aktif yang Dieksekusi CPU ({Object.keys(funcObj.functions || {}).length} Fungsi):
                          </span>
                          <span className="text-[10px] font-mono text-rose-500 font-bold">
                            Protokol SC737 Svc 1 / Objek 6 (Active Functions)
                          </span>
                        </div>

                        {Object.keys(funcObj.functions || {}).length === 0 ? (
                          <div className="p-8 text-center text-gray-400 italic bg-gray-50/50 dark:bg-meta-4/20 rounded-lg border border-dashed border-stroke dark:border-strokedark">
                            {iwLoading ? 'Sedang membaca fungsi langkah aktif...' : 'Tidak ada fungsi resep aktif yang sedang berjalan di kontroler'}
                          </div>
                        ) : (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {Object.entries(funcObj.functions).map(([key, f]) => (
                              <div key={key} className="border border-stroke dark:border-strokedark rounded-lg p-4 bg-white dark:bg-boxdark space-y-3">
                                <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-500/15 text-rose-500 font-mono">
                                      Fungsi {f.function_id}
                                    </span>
                                    <span className="text-xs font-bold text-black dark:text-white">
                                      {f.function_name}
                                    </span>
                                  </div>
                                  <span className="text-[10px] font-mono text-gray-400">
                                    Langkah: Baris #{f.line}
                                  </span>
                                </div>

                                <div className="grid grid-cols-2 gap-2 text-xs">
                                  {(f.parameters || []).map((p) => (
                                    <div key={p.param_no} className="p-2 rounded bg-gray-50 dark:bg-meta-4/40 border border-stroke dark:border-strokedark">
                                      <div className="text-[10px] text-gray-400 truncate">
                                        P{p.param_no}: {p.name}
                                      </div>
                                      <div className="text-base font-bold font-mono text-black dark:text-white mt-0.5">
                                        {p.value} <span className="text-xs font-normal text-gray-500">{p.unit}</span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* ======================================================= */}
                    {/* TAB 5: OBJEK 1035 - KONSUMSI BATCH (DWORD 32-BIT)       */}
                    {/* ======================================================= */}
                    {iwActiveTab === '1035_batch' && (
                      <div className="space-y-3">
                        <div className="bg-gray-50 dark:bg-meta-4 px-4 py-2 border border-stroke dark:border-strokedark rounded-lg flex items-center justify-between">
                          <span className="text-xs font-bold text-black dark:text-white">
                            Akumulasi Konsumsi Sumber Daya Batch (DWORD 32-bit):
                          </span>
                          <span className="text-[10px] font-mono text-amber-500 font-bold">
                            Protokol SC737 Svc 11 / Objek 1035 (BATCH)
                          </span>
                        </div>

                        {batchCounters.length === 0 ? (
                          <div className="p-8 text-center text-gray-400 italic bg-gray-50/50 dark:bg-meta-4/20 rounded-lg border border-dashed border-stroke dark:border-strokedark">
                            {iwLoading ? 'Sedang membaca akumulasi konsumsi batch...' : 'Tidak ada counter konsumsi yang tersedia'}
                          </div>
                        ) : (
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            {batchCounters.map((c) => (
                              <div key={c.index} className="p-3.5 rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark shadow-2xs">
                                <div className="text-[11px] font-bold text-gray-500 uppercase flex items-center justify-between">
                                  <span>{c.name}</span>
                                  <Database className="h-4 w-4 text-amber-500" />
                                </div>
                                <div className="text-xl font-black font-mono text-black dark:text-white mt-1">
                                  {c.formatted}
                                </div>
                                <div className="text-[10px] text-gray-400 font-mono mt-0.5">
                                  Counter #{c.index} (Nilai Mentah: {c.value})
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                );
              })()}
            </div>

            {/* Footer */}
            <div className="bg-gray-100 dark:bg-meta-4 px-5 py-3 border-t border-stroke dark:border-strokedark flex items-center justify-between shrink-0">
              <span className="text-xs text-gray-500 font-mono">
                Port: 50000 | Protokol: SETEX SC737 | Format: Little-Endian | Dukungan Objek: 1025 (IW), 1009 (SET), 1010 (ACT), 1035 (BATCH), 6 (FUNC)
              </span>
              <button
                onClick={() => setShowIwModal(false)}
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
