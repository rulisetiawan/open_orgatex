import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Tv,
  LineChart,
  Bell,
  Calendar,
  Kanban,
  FileCode,
  Settings,
  Layers,
  Server,
  ListFilter,
  Clock,
  Tags
} from 'lucide-react';

const Sidebar = ({ sidebarOpen, setSidebarOpen }) => {
  const location = useLocation();
  const { pathname } = location;

  const menuGroups = [
    {
      groupTitle: 'MONITORING',
      items: [
        {
          name: 'Process Picture',
          path: '/',
          icon: Tv
        },
        {
          name: 'Process Analyser',
          path: '/process-analyser',
          icon: LineChart
        },
        {
          name: 'Riwayat Batch',
          path: '/batch-history',
          icon: Clock
        },
        {
          name: 'Alarm Monitor',
          path: '/alarms',
          icon: Bell
        },
        {
          name: 'FTP Explorer',
          path: '/ftp',
          icon: Server
        },
      ]
    },
    {
      groupTitle: 'PLANNING',
      items: [
        {
          name: 'Batch Pool',
          path: '/planning/list',
          icon: ListFilter
        },
        {
          name: 'Kanban Board',
          path: '/planning/kanban',
          icon: Kanban
        },
        {
          name: 'Kalender Produksi',
          path: '/planning/calendar',
          icon: Calendar
        },
      ]
    },
    {
      groupTitle: 'PROGRAM',
      items: [
        {
          name: 'Program Studio',
          path: '/programs',
          icon: FileCode
        },
      ]
    },
    {
      groupTitle: 'PENGATURAN',
      items: [
        {
          name: 'Konfigurasi Mesin',
          path: '/machines',
          icon: Settings
        },
        {
          name: 'Tag Mapping & IW',
          path: '/tag-mapping',
          icon: Tags
        },
      ]
    }
  ];

  return (
    <aside
      className={`fixed lg:static top-0 left-0 z-9999 flex h-screen w-72 flex-col overflow-y-hidden border-r border-stroke bg-white dark:border-strokedark dark:bg-[#0c1520] transition-all duration-300 ease-in-out ${sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
        }`}
    >
      {/* SIDEBAR HEADER */}
      <div className="flex items-center justify-between gap-3 px-6 py-4.5 border-b border-stroke dark:border-strokedark">
        <NavLink to="/" className="flex items-center gap-3 group">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-white shadow-sm group-hover:scale-105 transition-transform">
            <Layers className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-tight text-black dark:text-white leading-tight">
              SMM
            </h1>
            <p className="text-[11px] text-body dark:text-bodydark font-medium">Digital Automation</p>
          </div>
        </NavLink>
      </div>

      {/* NAVIGATION GROUPS */}
      <div className="no-scrollbar flex flex-col overflow-y-auto py-3 flex-1">
        <nav className="px-3 space-y-5">
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
                        className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-150 ${isActive
                          ? 'bg-primary text-white shadow-xs font-bold'
                          : 'text-body dark:text-bodydark hover:bg-gray dark:hover:bg-meta-4/60 hover:text-black dark:hover:text-white'
                          }`}
                      >
                        <Icon className={`h-4.5 w-4.5 shrink-0 transition-colors ${isActive ? 'text-white' : 'text-body dark:text-bodydark group-hover:text-primary dark:group-hover:text-secondary'
                          }`} />
                        <span className="truncate">{item.name}</span>
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
