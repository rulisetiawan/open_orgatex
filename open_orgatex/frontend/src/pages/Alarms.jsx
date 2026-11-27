import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Calendar,
  Filter,
  UserCheck,
  CalendarDays,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  Cpu,
  ShieldAlert,
  Clock
} from 'lucide-react';

const API_BASE = '/api';

const Alarms = () => {
  const location = useLocation();
  const initialMachineFromUrl = new URLSearchParams(location.search).get('machine');

  const [machines, setMachines] = useState([]);
  const [selectedMachine, setSelectedMachine] = useState(initialMachineFromUrl || '1A');
  const [alarms, setAlarms] = useState([]);
  const [availableDates, setAvailableDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [sortOrder, setSortOrder] = useState('desc');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');

  // Ambil daftar mesin sekali saat halaman dibuka (tanpa polling realtime)
  useEffect(() => {
    fetch(`${API_BASE}/machines/`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const sorted = [...data].sort((a, b) =>
            (a.machine_no || '').localeCompare(b.machine_no || '', undefined, {
              numeric: true,
              sensitivity: 'base',
            })
          );
          setMachines(sorted);
          const urlMach = new URLSearchParams(window.location.search).get('machine');
          const machNos = sorted.map((m) => m.machine_no);
          if (urlMach && machNos.includes(urlMach)) {
            setSelectedMachine(urlMach);
          } else if (!machNos.includes(selectedMachine)) {
            setSelectedMachine(sorted[0].machine_no);
          }
        }
      })
      .catch((err) => console.error('Gagal memuat daftar mesin:', err));
  }, []);

  // Ambil data alarm secara manual / saat filter berubah (TIDAK REALTIME / tanpa interval)
  const fetchAlarms = useCallback(
    async (
      mach = selectedMachine,
      dateFilter = selectedDate,
      cat = categoryFilter,
      sortOrd = sortOrder
    ) => {
      if (!mach) return;
      setLoading(true);
      try {
        const q = new URLSearchParams();
        if (dateFilter) q.append('date', dateFilter);
        if (cat && cat !== 'ALL') q.append('category', cat);
        q.append('order_by', 'datetime');
        q.append('order', sortOrd);
        q.append('limit', '500');

        const res = await fetch(`${API_BASE}/logs/alarms/${mach}?${q.toString()}`);
        if (res.ok) {
          const data = await res.json();
          setAlarms(Array.isArray(data.alarms) ? data.alarms : []);
          if (Array.isArray(data.available_dates)) {
            setAvailableDates(data.available_dates);
          }
          setLastUpdated(new Date().toLocaleTimeString('id-ID'));
        }
      } catch (err) {
        console.error('Gagal mengambil data alarm:', err);
      } finally {
        setLoading(false);
      }
    },
    [selectedMachine, selectedDate, categoryFilter, sortOrder]
  );

  useEffect(() => {
    fetchAlarms(selectedMachine, selectedDate, categoryFilter, sortOrder);
  }, [selectedMachine, selectedDate, categoryFilter, sortOrder, fetchAlarms]);

  const isInterventionItem = (al) =>
    Boolean(al.is_intervention || ['0', '20', '256', '5899'].includes(String(al.alarm_code)));

  const stats = useMemo(() => {
    let systemCount = 0;
    let interventionCount = 0;
    let criticalCount = 0;
    alarms.forEach((a) => {
      if (isInterventionItem(a)) interventionCount += 1;
      else systemCount += 1;
      if (String(a.severity || '').toUpperCase() === 'CRITICAL') criticalCount += 1;
    });
    return {
      total: alarms.length,
      systemCount,
      interventionCount,
      criticalCount,
    };
  }, [alarms]);

  const filteredAlarms = useMemo(() => {
    let list = [...alarms];

    if (selectedDate) {
      list = list.filter((ev) => {
        const evDate = ev.date || (ev.timestamp || ev.alarm_timestamp || '').slice(0, 10);
        return !evDate || evDate === selectedDate;
      });
    }

    if (categoryFilter === 'ALARM') {
      list = list.filter((ev) => !isInterventionItem(ev));
    } else if (categoryFilter === 'INTERVENTION') {
      list = list.filter((ev) => isInterventionItem(ev));
    }

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      list = list.filter((al) => {
        const hay = `${al.alarm_code || ''} ${al.alarm_title || ''} ${al.alarm_text || ''} ${al.alarm_detail || ''} ${al.description || ''} ${al.batch_no || ''} ${al.step_no || ''}`.toLowerCase();
        return hay.includes(q);
      });
    }

    list.sort((a, b) => {
      const rawA = a.timestamp || a.alarm_timestamp || '';
      const rawB = b.timestamp || b.alarm_timestamp || '';
      const tA = rawA ? new Date(rawA.replace(' ', 'T')).getTime() : 0;
      const tB = rawB ? new Date(rawB.replace(' ', 'T')).getTime() : 0;
      return sortOrder === 'asc' ? tA - tB : tB - tA;
    });

    return list;
  }, [alarms, selectedDate, categoryFilter, searchTerm, sortOrder]);

  const selectedMachineInfo = useMemo(
    () => machines.find((m) => m.machine_no === selectedMachine),
    [machines, selectedMachine]
  );

  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="space-y-5">
      {/* HEADER HALAMAN */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 bg-white dark:bg-boxdark p-4 sm:p-5 rounded-xl border border-stroke dark:border-strokedark shadow-sm">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-500">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg sm:text-xl font-bold tracking-tight text-black dark:text-white">
                  Alarm Monitor & Intervensi HMI
                </h2>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-meta-4 text-slate-600 dark:text-slate-300 border border-stroke dark:border-strokedark">
                  <Clock className="h-3 w-3" />
                  Mode Manual (Non-Realtime)
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {selectedMachineInfo
                  ? `${selectedMachineInfo.display_name || selectedMachine} · ${selectedMachineInfo.group_name || '-'} · IP ${selectedMachineInfo.ip_address || '-'}`
                  : `Mesin ${selectedMachine}`}
                {lastUpdated ? ` · Diperbarui pukul ${lastUpdated}` : ''}
              </p>
            </div>
          </div>
        </div>

        {/* PILIH MESIN & TOMBOL REFRESH MANUAL */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-2 bg-gray-50 dark:bg-meta-4/50 px-3 py-1.5 rounded-lg border border-stroke dark:border-strokedark">
            <Cpu className="h-4 w-4 text-primary shrink-0" />
            <label htmlFor="alarm-machine-select" className="text-xs font-semibold text-gray-500 dark:text-gray-400">
              Mesin:
            </label>
            <select
              id="alarm-machine-select"
              value={selectedMachine}
              onChange={(e) => {
                setSelectedMachine(e.target.value);
                setSelectedDate('');
              }}
              className="bg-transparent text-xs font-bold font-mono text-black dark:text-white outline-none cursor-pointer"
            >
              {machines.length > 0 ? (
                machines.map((m) => (
                  <option
                    key={m.machine_no}
                    value={m.machine_no}
                    className="bg-white dark:bg-boxdark text-black dark:text-white"
                  >
                    {m.machine_no} — {m.display_name || m.machine_no} ({m.group_name || '-'})
                  </option>
                ))
              ) : (
                <option value={selectedMachine}>{selectedMachine}</option>
              )}
            </select>
          </div>

          <button
            type="button"
            onClick={() => fetchAlarms()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-bold shadow-xs transition disabled:opacity-60 cursor-pointer"
            title="Muat ulang data alarm dari database"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Memuat...' : 'Refresh Data'}</span>
          </button>
        </div>
      </div>

      {/* RINGKASAN KARTU KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark p-4 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Total Catatan
          </div>
          <div className="text-2xl font-bold font-mono text-black dark:text-white mt-1">
            {stats.total}
          </div>
        </div>
        <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark p-4 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
            Alarm Sistem
          </div>
          <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400 mt-1">
            {stats.systemCount}
          </div>
        </div>
        <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark p-4 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">
            Intervensi Operator
          </div>
          <div className="text-2xl font-bold font-mono text-blue-600 dark:text-blue-400 mt-1">
            {stats.interventionCount}
          </div>
        </div>
        <div className="bg-white dark:bg-boxdark rounded-xl border border-stroke dark:border-strokedark p-4 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-danger">
            Tingkat Critical
          </div>
          <div className="text-2xl font-bold font-mono text-danger mt-1">
            {stats.criticalCount}
          </div>
        </div>
      </div>

      {/* PANEL TABEL ALARM & FILTER */}
      <div className="rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark shadow-sm overflow-hidden">
        {/* TOOLBAR FILTER TANGGAL & SORT */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between py-3.5 px-5 border-b border-stroke dark:border-strokedark gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="h-4 w-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Cari kode alarm, deskripsi, atau nomor batch..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-stroke dark:border-strokedark bg-gray-50 dark:bg-meta-4/40 text-black dark:text-white outline-none focus:border-primary"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 bg-gray-50 dark:bg-meta-4/40 px-2.5 py-1.5 rounded-lg border border-stroke dark:border-strokedark">
              <Calendar className="h-3.5 w-3.5 text-primary" />
              <span className="text-[11px] font-semibold text-gray-600 dark:text-gray-300">Tanggal:</span>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="text-xs font-mono font-bold text-black dark:text-white bg-transparent outline-none cursor-pointer"
              />
              {selectedDate && (
                <button
                  type="button"
                  onClick={() => setSelectedDate('')}
                  className="text-gray-400 hover:text-danger ml-1 p-0.5"
                  title="Hapus filter tanggal"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => setSelectedDate(todayStr)}
              className={`px-2.5 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
                selectedDate === todayStr
                  ? 'bg-primary text-white border-primary shadow-xs'
                  : 'bg-white dark:bg-boxdark text-gray-700 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-100 dark:hover:bg-meta-4'
              }`}
            >
              Hari Ini
            </button>

            <button
              type="button"
              onClick={() => setSelectedDate('')}
              className={`px-2.5 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
                !selectedDate
                  ? 'bg-primary text-white border-primary shadow-xs'
                  : 'bg-white dark:bg-boxdark text-gray-700 dark:text-gray-300 border-stroke dark:border-strokedark hover:bg-gray-100 dark:hover:bg-meta-4'
              }`}
            >
              Semua Tanggal
            </button>

            <button
              type="button"
              onClick={() => setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-boxdark hover:bg-gray-100 dark:hover:bg-meta-4 text-black dark:text-white"
              title="Ubah urutan kronologis Date Time"
            >
              <ArrowUpDown className="h-3.5 w-3.5 text-primary" />
              <span className="font-mono text-[11px] text-primary font-bold">
                {sortOrder === 'desc' ? 'Terbaru ↓' : 'Terlama ↑'}
              </span>
            </button>
          </div>
        </div>

        {/* SUB-BAR KATEGORI & TANGGAL ARSIP */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 bg-gray-50/60 dark:bg-meta-4/20 border-b border-stroke dark:border-strokedark text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-gray-500 mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3" /> Filter Tipe:
            </span>
            <button
              type="button"
              onClick={() => setCategoryFilter('ALL')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors ${
                categoryFilter === 'ALL'
                  ? 'bg-primary text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Semua ({stats.total})
            </button>
            <button
              type="button"
              onClick={() => setCategoryFilter('ALARM')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors ${
                categoryFilter === 'ALARM'
                  ? 'bg-amber-500 text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Alarm Sistem ({stats.systemCount})
            </button>
            <button
              type="button"
              onClick={() => setCategoryFilter('INTERVENTION')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors ${
                categoryFilter === 'INTERVENTION'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-boxdark border border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white'
              }`}
            >
              Intervensi Operator ({stats.interventionCount})
            </button>
          </div>

          {availableDates.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 shrink-0">
                <CalendarDays className="h-3 w-3" /> Tanggal Arsip:
              </span>
              {availableDates.slice(0, 10).map((dt) => (
                <button
                  type="button"
                  key={dt}
                  onClick={() => setSelectedDate(dt)}
                  className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold border transition-colors shrink-0 ${
                    selectedDate === dt
                      ? 'bg-primary text-white border-primary shadow-xs'
                      : 'bg-white dark:bg-boxdark border-stroke dark:border-strokedark text-gray-600 dark:text-gray-400 hover:border-primary'
                  }`}
                >
                  {dt}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* TABEL ALARM */}
        <div className="p-4 overflow-x-auto">
          {loading && filteredAlarms.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <RefreshCw className="h-6 w-6 animate-spin text-primary mb-2" />
              <p className="text-xs font-medium">Memuat data alarm Mesin {selectedMachine}...</p>
            </div>
          ) : filteredAlarms.length > 0 ? (
            <div className="space-y-3">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stroke dark:border-strokedark text-gray-500">
                    <th
                      onClick={() => setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
                      className="py-2.5 px-4 font-bold cursor-pointer hover:bg-gray-100 dark:hover:bg-meta-4/40 select-none transition-colors"
                    >
                      <div className="flex items-center gap-1.5 text-black dark:text-white">
                        <span>Tanggal & Waktu Kejadian</span>
                        <div className="flex items-center text-primary">
                          {sortOrder === 'desc' ? (
                            <ArrowDown className="h-3.5 w-3.5" />
                          ) : (
                            <ArrowUp className="h-3.5 w-3.5" />
                          )}
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
                  {filteredAlarms.map((al, idx) => {
                    const isInterv = isInterventionItem(al);
                    const rawTs = al.timestamp || al.alarm_timestamp || '';
                    const [dPart, tPart] = rawTs.includes(' ')
                      ? rawTs.split(' ')
                      : [al.date || rawTs, al.time || ''];

                    return (
                      <tr key={al.id || idx} className="hover:bg-gray-50 dark:hover:bg-meta-4/20 transition-colors">
                        <td className="py-2.5 px-4 font-mono">
                          <div className="flex flex-col">
                            <span className="font-bold text-black dark:text-white flex items-center gap-1">
                              <Calendar className="h-3 w-3 text-primary inline" />
                              {dPart || '-'}
                            </span>
                            <span className="text-[11px] text-gray-500">{tPart}</span>
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
                          <div className="flex flex-col gap-0.5">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold">
                                {al.alarm_title || al.alarm_text || al.description || `Gangguan Kode #${al.alarm_code}`}
                              </span>
                              {al.batch_no && (
                                <span className="text-[10px] font-mono text-gray-400">
                                  (Batch: #{al.batch_no})
                                </span>
                              )}
                            </div>
                            {al.alarm_detail &&
                              al.alarm_detail.toLowerCase() !== (al.alarm_title || '').toLowerCase() && (
                                <span className="text-[11px] font-normal text-gray-600 dark:text-gray-400">
                                  {al.alarm_detail}
                                </span>
                              )}
                            {al.alarm_found && al.alarm_source && (
                              <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500">
                                Sumber: {al.alarm_source}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              al.severity === 'CRITICAL'
                                ? 'bg-danger/10 text-danger border border-danger/20'
                                : al.severity === 'INFO'
                                  ? 'bg-success/10 text-success border border-success/20'
                                  : 'bg-warning/10 text-warning border border-warning/20'
                            }`}
                          >
                            {al.severity || 'WARNING'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-[11px] text-gray-500 pt-2 border-t border-stroke dark:border-strokedark px-1">
                <span>
                  Menampilkan <strong className="text-black dark:text-white">{filteredAlarms.length}</strong> catatan
                  {selectedDate ? ` pada tanggal ${selectedDate}` : ' dari seluruh arsip'} untuk Mesin {selectedMachine}.
                </span>
                {selectedDate && (
                  <button
                    type="button"
                    onClick={() => setSelectedDate('')}
                    className="text-primary hover:underline font-semibold"
                  >
                    Tampilkan Semua Tanggal →
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              <CheckCircle2 className="h-8 w-8 text-success mx-auto mb-2" />
              <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                {selectedDate
                  ? `Tidak ada riwayat alarm atau intervensi HMI Mesin ${selectedMachine} pada tanggal ${selectedDate}.`
                  : `Tidak ada catatan alarm untuk Mesin ${selectedMachine}.`}
              </p>
              <p className="text-[11px] text-gray-400 mt-1">
                Klik tombol <strong>Refresh Data</strong> untuk memuat ulang secara manual.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Alarms;
