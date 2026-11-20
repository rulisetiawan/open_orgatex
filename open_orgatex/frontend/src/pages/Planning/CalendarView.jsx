import React from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';

const CalendarView = () => {
  const events = [
    {
      id: '1',
      title: 'TD12: #061118 (Reactive Cotton)',
      start: new Date().toISOString().split('T')[0] + 'T08:00:00',
      end: new Date().toISOString().split('T')[0] + 'T10:15:00',
      backgroundColor: '#465fff',
      borderColor: '#465fff',
    },
    {
      id: '2',
      title: 'TD12: #061119 (Direct Black)',
      start: new Date().toISOString().split('T')[0] + 'T10:30:00',
      end: new Date().toISOString().split('T')[0] + 'T12:30:00',
      backgroundColor: '#f59e0b',
      borderColor: '#f59e0b',
    },
    {
      id: '3',
      title: 'TD13: #061120 (Scouring)',
      start: new Date().toISOString().split('T')[0] + 'T09:00:00',
      end: new Date().toISOString().split('T')[0] + 'T10:30:00',
      backgroundColor: '#10b981',
      borderColor: '#10b981',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl md:text-2xl font-bold tracking-tight text-black dark:text-white">
          Kalender Produksi
        </h2>
      </div>

      <div className="rounded-xl border border-stroke bg-white p-5 shadow-sm dark:border-strokedark dark:bg-boxdark">
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
          height="650px"
        />
      </div>
    </div>
  );
};

export default CalendarView;
