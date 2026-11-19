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
  FileText, 
  Settings, 
  Layers,
  Database,
  Server,
  ListFilter
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
        /* Disembunyikan sementara agar tidak membingungkan:
        { 
          name: 'Program OrgaTEX (EDX300)', 
          sub: 'Modular Procedure & Treatments', 
          path: '/programs-edx', 
          icon: Layers 
        },
        */
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
      className={`absolute left-0 top-0 z-9999 flex h-screen w-72.5 flex-col overflow-y-hidden bg-[#1c2434] duration-300 ease-linear dark:bg-boxdark lg:static lg:translate-x-0 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      {/* SIDEBAR HEADER */}
      <div className="flex items-center justify-between gap-2 px-6 py-5.5 border-b border-gray-700/50">
        <NavLink to="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white shadow-md">
            <Layers className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-xl font-bold tracking-wide text-white">OrgaTEX</h1>
              <span className="text-[10px] bg-primary/30 text-primary border border-primary/50 px-1.5 py-0.2 rounded font-semibold">WEB</span>
            </div>
            <p className="text-[10px] text-gray-400">SETEX Workplace 2.0 Parity</p>
          </div>
        </NavLink>
      </div>

      <div className="no-scrollbar flex flex-col overflow-y-auto duration-300 ease-linear py-4">
        <nav className="px-4 lg:px-5 space-y-6">
          {menuGroups.map((group, gIdx) => (
            <div key={gIdx}>
              <h3 className="mb-2 ml-3 text-[11px] font-bold uppercase tracking-wider text-gray-400">
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
                        className={`group relative flex items-center gap-3 rounded px-3.5 py-2 font-medium duration-200 ease-in-out ${
                          isActive
                            ? 'bg-primary text-white shadow-sm'
                            : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                        }`}
                      >
                        <Icon className={`h-4.5 w-4.5 shrink-0 ${isActive ? 'text-white' : 'text-gray-400 group-hover:text-white'}`} />
                        <div className="flex flex-col min-w-0">
                          <span className="text-xs font-semibold leading-tight truncate">{item.name}</span>
                          <span className={`text-[10px] leading-tight truncate ${isActive ? 'text-blue-100' : 'text-gray-400'}`}>{item.sub}</span>
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
