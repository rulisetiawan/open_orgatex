import React, { useState, useEffect, useCallback, useMemo } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import { RefreshCw, Calendar as CalendarIcon, X, Layers, Cpu, Droplet } from 'lucide-react';
import { api, getApiErrorMessage } from '../../services/api';
import { useToast } from '../../context/ToastContext';

const STATUS_COLORS = {
  PLANNING: '#8b5cf6',
  QUEUED: '#f59e0b',
  WAITING_LA: '#3b82f6',
  RUNNING: '#10b981',
  COMPLETED: '#64748b',
  HOLD: '#ef4444',
};

const CalendarView = () => {
  const { toast } = useToast();
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const fetchBatches = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/planning/');
      setBatches(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      toast.error(`Gagal memuat jadwal produksi: ${getApiErrorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchBatches();
  }, [fetchBatches]);

  // Map planning batches to calendar events grouped sequentially per machine
  const events = useMemo(() => {
    const todayBase = new Date();
    todayBase.setHours(7, 0, 0, 0);
    const machineOffsets = {};

    return batches.map((b, idx) => {
      const mach = b.machine_no || 'UNASSIGNED';
      const offsetHours = machineOffsets[mach] || 0;
      machineOffsets[mach] = offsetHours + 2.5;

      const startDt = b.scheduled_start
        ? new Date(b.scheduled_start)
        : new Date(todayBase.getTime() + offsetHours * 3600 * 1000);
      const endDt = b.scheduled_end
        ? new Date(b.scheduled_end)
        : new Date(startDt.getTime() + 2 * 3600 * 1000);

      const color = STATUS_COLORS[(b.status || 'PLANNING').toUpperCase()] || '#465fff';
      return {
        id: String(b.id || idx),
        title: `${mach}: #${b.batch_no || b.reference_no || idx + 1} (${b.recipe_name || 'Resep'})`,
        start: startDt.toISOString(),
        end: endDt.toISOString(),
        backgroundColor: color,
        borderColor: color,
        extendedProps: { batch: b },
      };
    });
  }, [batches]);

  // Close modal on Escape
  useEffect(() => {
    if (!selectedEvent) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setSelectedEvent(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedEvent]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl md:text-2xl font-bold tracking-tight text-black dark:text-white flex items-center gap-2">
            <CalendarIcon className="h-6 w-6 text-primary" />
            Kalender Produksi
          </h2>
          <p className="text-xs text-body dark:text-bodydark mt-0.5">
            Jadwal antrean batch produksi per mesin ({batches.length} batch terdaftar)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold mr-2">
            {Object.entries(STATUS_COLORS).map(([status, color]) => (
              <span key={status} className="inline-flex items-center gap-1 text-body dark:text-bodydark">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                {status}
              </span>
            ))}
          </div>
          <button
            type="button"
            onClick={fetchBatches}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white dark:bg-boxdark border border-stroke dark:border-strokedark hover:bg-gray dark:hover:bg-meta-4 text-black dark:text-white shadow-xs transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Segarkan
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-stroke bg-white p-4 sm:p-5 shadow-sm dark:border-strokedark dark:bg-boxdark">
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="timeGridDay"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridDay,timeGridWeek,dayGridMonth',
          }}
          slotMinTime="06:00:00"
          slotMaxTime="23:00:00"
          allDaySlot={false}
          events={events}
          eventClick={(info) => {
            const batch = info.event.extendedProps?.batch;
            if (batch) setSelectedEvent(batch);
          }}
          height="650px"
        />
      </div>

      {/* Event Detail Modal */}
      {selectedEvent && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Detail Jadwal Batch"
          onClick={() => setSelectedEvent(null)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark p-5 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-stroke dark:border-strokedark pb-3">
              <h3 className="text-sm font-bold text-black dark:text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-primary" />
                Batch #{selectedEvent.batch_no || selectedEvent.reference_no}
              </h3>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                aria-label="Tutup detail batch"
                className="p-1 rounded-lg text-gray-400 hover:text-black dark:hover:text-white hover:bg-gray dark:hover:bg-meta-4 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark flex items-center gap-1"><Cpu className="h-3.5 w-3.5" /> Mesin:</span>
                <span className="font-mono font-bold text-primary">{selectedEvent.machine_no}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark">Program / Resep:</span>
                <span className="font-semibold text-black dark:text-white text-right">
                  M_{String(selectedEvent.program_no || 1).padStart(4, '0')}.PRG · {selectedEvent.recipe_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark">Customer / Artikel:</span>
                <span className="font-medium text-black dark:text-white text-right">
                  {selectedEvent.customer || '-'} / {selectedEvent.article || '-'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark">Warna:</span>
                <span className="font-medium text-black dark:text-white">
                  {selectedEvent.color_name || '-'} ({selectedEvent.color_code || '-'})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark flex items-center gap-1"><Droplet className="h-3.5 w-3.5" /> Berat / LR:</span>
                <span className="font-mono font-bold text-black dark:text-white">
                  {selectedEvent.fabric_weight_kg || 0} kg (1:{selectedEvent.liquor_ratio || 8})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-body dark:text-bodydark">Status:</span>
                <span className="font-mono font-bold px-2 py-0.5 rounded bg-primary/10 text-primary">
                  {selectedEvent.status}
                </span>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-stroke dark:border-strokedark">
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-gray dark:bg-meta-4 text-black dark:text-white hover:bg-gray-200 dark:hover:bg-meta-4/80 transition"
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

export default CalendarView;
