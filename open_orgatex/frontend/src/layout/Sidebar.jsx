import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  Tv, 
  LineChart, 
  Bell, 
  Calendar, 
  Kanban, 
  FlaskConical, 
  FileCode, 
  Settings, 
  Layers,
  Server, 
  ListFilter,
  Clock
} from 'lucide-react';

const Sidebar = ({ sidebarOpen, setSidebarOpen }) => {
  const location = useLocation();
  const { pathname } = location;

  const menuGroups = [
    {
      groupTitle: 'SUPERVISION & MONITORING',
      items: [
        { 
          name: 'Process Picture (Online)', 
          sub: 'OLN420 Machine Mimic', 
          path: '/', 
          icon: Tv 
        },
        { 
          name: 'Process Analyser', 
          sub: 'FEN240 Telemetri & Kurva', 
          path: '/process-analyser', 
          icon: LineChart 
        },
        { 
          name: 'Riwayat Batch', 
          sub: 'Arsip & Kurva Batch Selesai', 
          path: '/batch-history', 
          icon: Clock 
        },
        { 
          name: 'Alarm Monitor', 
          sub: 'RCX710 Gangguan & Stop', 
          path: '/alarms', 
          icon: Bell 
        },
        { 
          name: 'FTP Controller Explorer', 
          sub: 'Transfer File Secom Port 21', 
          path: '/ftp', 
          icon: Server 
        },
      ]
    },
    {
      groupTitle: 'PRODUCTION PLANNING (SCX620)',
      items: [
        { 
          name: 'Batch Pool (Tabel)', 
          sub: 'Daftar Antrean & Dispatch', 
          path: '/planning/list', 
          icon: ListFilter 
        },
        { 
          name: 'Batch Kanban Board', 
          sub: 'Tahapan Workflow Celup', 
          path: '/planning/kanban', 
          icon: Kanban 
        },
        { 
          name: 'Production Calendar', 
          sub: 'Shift & Hari Kerja', 
          path: '/planning/calendar', 
          icon: Calendar 
        },
      ]
    },
    {
      groupTitle: 'EDITOR & PROCEDURES',
      items: [
        { 
          name: 'Program SECOM Studio', 
          sub: 'Linear Step-by-Step 65B PRG', 
          path: '/programs', 
          icon: FileCode 
        },
        { 
          name: 'Formula Editor', 
          sub: 'FEN240 Recipe Formulas', 
          path: '/recipes', 
          icon: FlaskConical 
        },
      ]
    },
    {
      groupTitle: 'CONFIGURATION & TOOLS',
      items: [
        { 
          name: 'Machine Configuration', 
          sub: 'OtxMachineConfigLib', 
          path: '/machines', 
          icon: Settings 
        },
      ]
    }
  ];

  return (
    <aside
      className={`fixed lg:static top-0 left-0 z-9999 flex h-screen w-72 flex-col overflow-y-hidden border-r border-stroke bg-white dark:border-strokedark dark:bg-[#0c1520] transition-all duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
      }`}
    >
      {/* SIDEBAR HEADER */}
      <div className="flex items-center justify-between gap-3 px-6 py-4.5 border-b border-stroke dark:border-strokedark">
        <NavLink to="/" className="flex items-center gap-3 group">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-white shadow-md group-hover:scale-105 transition-transform">
            <Layers className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h1 className="text-sm font-extrabold tracking-tight text-black dark:text-white leading-tight">
                SMM digital otomation
              </h1>
              <span className="text-[9px] bg-primary/10 text-primary border border-primary/20 dark:bg-primary/20 dark:text-secondary px-1.5 py-0.2 rounded font-bold">
                MES
              </span>
            </div>
            <p className="text-[11px] text-body dark:text-bodydark font-medium">SETEX Workplace 2.0</p>
          </div>
        </NavLink>
      </div>

      {/* NAVIGATION GROUPS */}
      <div className="no-scrollbar flex flex-col overflow-y-auto py-4 flex-1">
        <nav className="px-3.5 space-y-6">
          {menuGroups.map((group, gIdx) => (
            <div key={gIdx}>
              <h3 className="mb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
                {group.groupTitle}
              </h3>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname === item.path || (item.path === '/process-analyser' && pathname === '/logs');
                  return (
                    <li key={item.path}>
                      <NavLink
                        to={item.path}
                        className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-150 ${
                          isActive
                            ? 'bg-primary text-white shadow-sm shadow-primary/30 font-bold'
                            : 'text-body dark:text-bodydark hover:bg-gray dark:hover:bg-meta-4/60 hover:text-black dark:hover:text-white'
                        }`}
                      >
                        <Icon className={`h-4.5 w-4.5 shrink-0 transition-colors ${
                          isActive ? 'text-white' : 'text-body dark:text-bodydark group-hover:text-primary dark:group-hover:text-secondary'
                        }`} />
                        <div className="flex flex-col min-w-0">
                          <span className="leading-tight truncate">{item.name}</span>
                          <span className={`text-[10px] font-normal leading-tight truncate mt-0.5 ${
                            isActive ? 'text-blue-100/90' : 'text-body/80 dark:text-bodydark2'
                          }`}>
                            {item.sub}
                          </span>
                        </div>
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;
