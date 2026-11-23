import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Tags, 
  Search, 
  RefreshCw, 
  Copy, 
  Check, 
  Radio, 
  Cpu, 
  Activity, 
  Gauge, 
  SlidersHorizontal,
  Server,
  Layers,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

const TagMapping = () => {
  const [machines, setMachines] = useState([]);
  const [selectedMachine, setSelectedMachine] = useState('10B');
  const [mappings, setMappings] = useState([]);
  const [liveMeta, setLiveMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [copiedTag, setCopiedTag] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // 1. Fetch available machines
  const fetchMachines = async () => {
    try {
      const res = await axios.get('/api/iw-telemetry/machines');
      if (res.data && res.data.data) {
        setMachines(res.data.data);
      }
    } catch (err) {
      console.error('Failed to fetch IW machines:', err);
    }
  };

  // 2. Fetch mapping and live data for selected machine
  const fetchMappingData = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setRefreshing(true);
    try {
      const res = await axios.get(`/api/iw-telemetry/mapping/${selectedMachine}`);
      if (res.data && res.data.data) {
        setMappings(res.data.data);
        setLiveMeta(res.data.live_meta);
      }
    } catch (err) {
      console.error(`Failed to fetch mappings for ${selectedMachine}:`, err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchMachines();
  }, []);

  useEffect(() => {
    fetchMappingData(true);
  }, [selectedMachine]);

  // Periodic Auto-refresh (every 3 seconds)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchMappingData(false);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedMachine]);

  const copyToClipboard = (tagName) => {
    navigator.clipboard.writeText(tagName);
    setCopiedTag(tagName);
    setTimeout(() => setCopiedTag(null), 2000);
  };

  // Filtered rows
  const filteredMappings = mappings.filter(item => {
    const matchesSearch = 
      item.tag_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.notes?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.field_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(item.register_index).includes(searchQuery) ||
      String(item.iw_number).includes(searchQuery);

    const matchesRole = roleFilter === 'ALL' || item.tag_role === roleFilter;

    return matchesSearch && matchesRole;
  });

  // Calculate statistics
  const totalTags = mappings.length;
  const totalPv = mappings.filter(m => m.tag_role === 'PV').length;
  const totalSv = mappings.filter(m => m.tag_role === 'SV').length;
  const totalSt = mappings.filter(m => m.tag_role === 'ST').length;

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-[#0c1520] p-5 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
        <div>
          <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider mb-1">
            <Tags className="h-4 w-4" />
            <span>Digital Automation SCADA Integration</span>
          </div>
          <h1 className="text-xl font-extrabold text-black dark:text-white tracking-tight">
            SETEX Info Words (IW) & Tag Mapping
          </h1>
          <p className="text-xs text-body dark:text-bodydark">
            Monitoring mapping register controller SETEX Object 1025 ke standard tag SCADA SMM
          </p>
        </div>

        {/* CONTROLS */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Machine Selector */}
          <div className="flex items-center gap-2 bg-gray dark:bg-meta-4/40 px-3 py-1.5 rounded-lg border border-stroke dark:border-strokedark">
            <Server className="h-4 w-4 text-primary" />
            <span className="text-xs font-semibold text-black dark:text-white">Mesin:</span>
            <select
              value={selectedMachine}
              onChange={(e) => setSelectedMachine(e.target.value)}
              className="bg-transparent text-xs font-bold text-black dark:text-white outline-none cursor-pointer"
            >
              {machines.length > 0 ? (
                machines.map(m => (
                  <option key={m.machine_no} value={m.machine_no} className="bg-white dark:bg-[#0c1520]">
                    {m.machine_no} - {m.display_name} ({m.total_mapped_tags} tags)
                  </option>
                ))
              ) : (
                <option value="10B">10B - Mesin 10B (Novatech)</option>
              )}
            </select>
          </div>

          {/* Auto Refresh Toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
              autoRefresh 
                ? 'bg-success/10 text-success border border-success/30' 
                : 'bg-gray dark:bg-meta-4/40 text-body dark:text-bodydark border border-stroke dark:border-strokedark'
            }`}
          >
            <Radio className={`h-3.5 w-3.5 ${autoRefresh ? 'animate-pulse text-success' : ''}`} />
            <span>Live Stream {autoRefresh ? 'ON (3s)' : 'PAUSED'}</span>
          </button>

          {/* Manual Refresh Button */}
          <button
            onClick={() => fetchMappingData(false)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold bg-primary text-white hover:bg-primary/90 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Segarkan</span>
          </button>
        </div>
      </div>

      {/* STATS OVERVIEW CARDS */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-[#0c1520] p-4 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-body dark:text-bodydark uppercase tracking-wider">Total Register</span>
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Cpu className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-black dark:text-white">{totalTags}</div>
          <p className="text-[10px] text-body dark:text-bodydark mt-0.5">Terkalibrasi dari TYPECONF</p>
        </div>

        <div className="bg-white dark:bg-[#0c1520] p-4 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-success uppercase tracking-wider">Actual Values (PV)</span>
            <div className="p-2 rounded-lg bg-success/10 text-success">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-success">{totalPv}</div>
          <p className="text-[10px] text-body dark:text-bodydark mt-0.5">Suhu, Level, Speed, Pressure</p>
        </div>

        <div className="bg-white dark:bg-[#0c1520] p-4 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-primary uppercase tracking-wider">Setpoints (SV)</span>
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Gauge className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-primary">{totalSv}</div>
          <p className="text-[10px] text-body dark:text-bodydark mt-0.5">Target Operasi Otomatis</p>
        </div>

        <div className="bg-white dark:bg-[#0c1520] p-4 rounded-xl border border-stroke dark:border-strokedark shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-warning uppercase tracking-wider">Koneksi Telemetry</span>
            <div className="p-2 rounded-lg bg-warning/10 text-warning">
              <Radio className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2 text-base font-extrabold text-black dark:text-white flex items-center gap-1.5">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${liveMeta ? 'bg-success animate-ping' : 'bg-gray-400'}`}></span>
            <span>{liveMeta ? 'ONLINE (Port 50000)' : 'STANDBY'}</span>
          </div>
          <p className="text-[10px] text-body dark:text-bodydark mt-0.5 truncate">
            {liveMeta?.last_updated ? new Date(liveMeta.last_updated).toLocaleTimeString() : 'Menunggu service collector'}
          </p>
        </div>
      </div>

      {/* FILTER & SEARCH BAR */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white dark:bg-[#0c1520] p-3 rounded-xl border border-stroke dark:border-strokedark">
        {/* Search Box */}
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-body dark:text-bodydark" />
          <input
            type="text"
            placeholder="Cari Tag SCADA, deskripsi parameter, register index, atau IW..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray dark:bg-meta-4/30 border border-stroke dark:border-strokedark rounded-lg pl-10 pr-4 py-2 text-xs text-black dark:text-white outline-none focus:border-primary transition-all"
          />
        </div>

        {/* Role Filters */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'ALL', label: `Semua (${totalTags})` },
            { id: 'PV', label: `Actual / PV (${totalPv})` },
            { id: 'SV', label: `Setpoint / SV (${totalSv})` },
            { id: 'ST', label: `Status / ST (${totalSt})` },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setRoleFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                roleFilter === tab.id
                  ? 'bg-primary text-white shadow-xs'
                  : 'bg-gray dark:bg-meta-4/40 text-body dark:text-bodydark hover:text-black dark:hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* DATA TABLE */}
      <div className="bg-white dark:bg-[#0c1520] rounded-xl border border-stroke dark:border-strokedark shadow-xs overflow-hidden">
        <div className="max-h-[650px] overflow-y-auto overflow-x-auto no-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 z-10 bg-gray-50 dark:bg-meta-4/70 backdrop-blur-md border-b border-stroke dark:border-strokedark text-[11px] font-bold uppercase text-body dark:text-bodydark tracking-wider">
              <tr>
                <th className="py-3.5 px-4 text-center w-20">Register / IW</th>
                <th className="py-3.5 px-4">Tag SCADA Digital Automation</th>
                <th className="py-3.5 px-4">Deskripsi Parameter (SETEX)</th>
                <th className="py-3.5 px-4 text-center w-24">Role</th>
                <th className="py-3.5 px-4 text-right">Rentang Kalibrasi</th>
                <th className="py-3.5 px-4 text-right bg-primary/5 dark:bg-primary/10">Nilai Live (Actual)</th>
                <th className="py-3.5 px-4 text-center w-24">Kualitas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke dark:divide-strokedark text-xs">
              {loading ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-body dark:text-bodydark">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
                    <span>Memuat mapping tag mesin {selectedMachine}...</span>
                  </td>
                </tr>
              ) : filteredMappings.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-body dark:text-bodydark">
                    <AlertCircle className="h-8 w-8 mx-auto mb-2 text-warning opacity-60" />
                    <span>Tidak ada tag yang sesuai dengan filter pencarian.</span>
                  </td>
                </tr>
              ) : (
                filteredMappings.map((row) => {
                  const isCopied = copiedTag === row.tag_name;
                  const hasLiveVal = row.live_value !== undefined && row.live_value !== null;
                  
                  return (
                    <tr 
                      key={row.id}
                      className="hover:bg-gray-50 dark:hover:bg-meta-4/20 transition-colors group"
                    >
                      {/* Register Index & IW Number */}
                      <td className="py-3 px-4 text-center font-mono font-bold text-black dark:text-white">
                        <div className="bg-gray dark:bg-meta-4/40 px-2 py-1 rounded text-[11px] border border-stroke dark:border-strokedark">
                          IW {row.iw_number}
                        </div>
                        <span className="text-[10px] text-body dark:text-bodydark font-normal">Idx {row.register_index}</span>
                      </td>

                      {/* Tag Name with Copy Button */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <code className="text-xs font-mono font-bold text-primary dark:text-primary/90 bg-primary/5 dark:bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                            {row.tag_name}
                          </code>
                          <button
                            onClick={() => copyToClipboard(row.tag_name)}
                            title="Salin Tag SCADA"
                            className="p-1 rounded hover:bg-gray dark:hover:bg-meta-4/60 text-body dark:text-bodydark hover:text-black dark:hover:text-white transition-colors"
                          >
                            {isCopied ? (
                              <Check className="h-3.5 w-3.5 text-success" />
                            ) : (
                              <Copy className="h-3.5 w-3.5 opacity-60 group-hover:opacity-100" />
                            )}
                          </button>
                        </div>
                        <div className="text-[10px] text-body dark:text-bodydark mt-0.5">
                          Field: <span className="font-mono">{row.field_name}</span>
                        </div>
                      </td>

                      {/* Notes / Description */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-black dark:text-white">
                          {row.notes?.split('(')[0] || row.field_name}
                        </div>
                        {row.notes?.includes('(') && (
                          <div className="text-[11px] text-body dark:text-bodydark italic">
                            {row.notes.split('(')[1]?.replace(')', '')}
                          </div>
                        )}
                      </td>

                      {/* Tag Role Badge */}
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
                          row.tag_role === 'PV'
                            ? 'bg-success/10 text-success border border-success/30'
                            : row.tag_role === 'SV'
                            ? 'bg-primary/10 text-primary border border-primary/30'
                            : 'bg-warning/10 text-warning border border-warning/30'
                        }`}>
                          {row.tag_role === 'PV' ? 'Actual (PV)' : row.tag_role === 'SV' ? 'Setpoint (SV)' : row.tag_role}
                        </span>
                      </td>

                      {/* Calibration Range */}
                      <td className="py-3 px-4 text-right font-mono text-[11px] text-body dark:text-bodydark">
                        <div>
                          <span className="text-black dark:text-white font-semibold">{row.eng_min}</span> ~ <span className="text-black dark:text-white font-semibold">{row.eng_max}</span> {row.unit}
                        </div>
                        <div className="text-[10px] opacity-75">
                          Raw: {row.raw_min}-{row.raw_max} (×{row.scale_factor})
                        </div>
                      </td>

                      {/* Live Value */}
                      <td className="py-3 px-4 text-right bg-primary/5 dark:bg-primary/10">
                        {hasLiveVal ? (
                          <div>
                            <span className="text-sm font-mono font-extrabold text-success">
                              {Number(row.live_value).toFixed(1)}
                            </span>
                            <span className="text-xs font-bold text-body dark:text-bodydark ml-1">
                              {row.unit}
                            </span>
                            <div className="text-[10px] text-body dark:text-bodydark font-mono">
                              Raw: {row.live_raw}
                            </div>
                          </div>
                        ) : (
                          <span className="text-[11px] text-body dark:text-bodydark italic">
                            --
                          </span>
                        )}
                      </td>

                      {/* Quality */}
                      <td className="py-3 px-4 text-center">
                        {hasLiveVal ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-success">
                            <CheckCircle2 className="h-3 w-3" />
                            <span>192 (Good)</span>
                          </span>
                        ) : (
                          <span className="text-[10px] text-body dark:text-bodydark opacity-50">
                            No Stream
                          </span>
                        )}
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

export default TagMapping;
