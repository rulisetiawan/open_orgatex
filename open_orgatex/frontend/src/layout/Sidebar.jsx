import React, { useEffect, useState, useCallback } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import api from '../services/api';
import useVisibilityInterval from '../hooks/useVisibilityInterval';
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
  Tags,
  ShieldAlert,
  Calculator,
  X
} from 'lucide-react';

const Sidebar = ({ sidebarOpen, setSidebarOpen }) => {
  const location = useLocation();
  const { pathname } = location;
  const [ftpUnreadableCount, setFtpUnreadableCount] = useState(0);

  const fetchFtpUnreadableCount = useCallback(async () => {
    try {
      const res = await api.get('/ftp/worker-status', {
        params: { include_inactive: false },
      });
      const summary = res.data?.summary;
      if (summary) {
        const count = Number(summary.ftp_unreadable_count ?? summary.ftp_failed_count ?? 0);
        setFtpUnreadableCount(Number.isFinite(count) ? count : 0);
      }
    } catch {
      // Abaikan error sementara agar sidebar tetap responsif
    }
  }, []);

  useEffect(() => {
    fetchFtpUnreadableCount();
  }, [fetchFtpUnreadableCount]);

  useVisibilityInterval(fetchFtpUnreadableCount, 30000);

  // Auto-close mobile drawer on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname, setSidebarOpen]);

  // Close mobile drawer on Escape
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [sidebarOpen, setSidebarOpen]);

  const menuGroups = [
    {
      groupTitle: 'MONITORING',
      items: [
        { name: 'Process Picture', path: '/', icon: Tv },
        { name: 'Process Analyser', path: '/process-analyser', icon: LineChart },
        { name: 'Riwayat Batch', path: '/batch-history', icon: Clock },
        { name: 'Alarm Monitor', path: '/alarms', icon: Bell },
        // Sementara disembunyikan agar tidak membuka koneksi FTP langsung ke kontroler
        // { name: 'FTP Explorer', path: '/ftp', icon: Server },
        {
          name: 'Status Baca FTP',
          path: '/ftp-monitor',
          icon: ShieldAlert,
          badgeCount: ftpUnreadableCount,
          badgeTitle: `${ftpUnreadableCount} mesin FTP tidak bisa diakses`,
        },
      ]
    },
    {
      groupTitle: 'PLANNING',
      items: [
        { name: 'Batch', path: '/planning/list', icon: ListFilter },
        { name: 'Planning Board', path: '/planning/kanban', icon: Kanban },
        { name: 'Kalender Produksi', path: '/planning/calendar', icon: Calendar },
      ]
    },
    {
      groupTitle: 'PROGRAM',
      items: [
        { name: 'Program Studio', path: '/programs', icon: FileCode },
        { name: 'Formula Parameter', path: '/formulas', icon: Calculator },
      ]
    },
    {
      groupTitle: 'PENGATURAN',
      items: [
        { name: 'Konfigurasi Mesin', path: '/machines', icon: Settings },
        { name: 'Tag Mapping & IW', path: '/tag-mapping', icon: Tags },
      ]
    }
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          aria-hidden="true"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs lg:hidden animate-in fade-in"
        />
      )}

      <aside
        aria-label="Navigasi Utama"
        className={`fixed lg:static top-0 left-0 z-50 lg:z-30 flex h-screen w-72 flex-col overflow-y-hidden border-r border-stroke bg-white dark:border-strokedark dark:bg-[#0c1520] transition-transform duration-300 ease-in-out ${
          sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
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
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Tutup navigasi"
            className="lg:hidden p-1.5 rounded-lg text-body dark:text-bodydark hover:bg-gray dark:hover:bg-meta-4 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* NAVIGATION GROUPS */}
        <div className="no-scrollbar flex flex-col overflow-y-auto py-3 flex-1">
          <nav className="px-3 space-y-5">
            {menuGroups.map((group) => (
              <div key={group.groupTitle}>
                <h3 className="mb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-body dark:text-bodydark2">
                  {group.groupTitle}
                </h3>
                <ul className="space-y-1">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive =
                      pathname === item.path ||
                      (item.path === '/process-analyser' && pathname === '/logs');
                    return (
                      <li key={item.path}>
                        <NavLink
                          to={item.path}
                          aria-current={isActive ? 'page' : undefined}
                          className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-150 ${
                            isActive
                              ? 'bg-primary text-white shadow-xs font-bold'
                              : 'text-body dark:text-bodydark hover:bg-gray dark:hover:bg-meta-4/60 hover:text-black dark:hover:text-white'
                          }`}
                        >
                          <Icon
                            className={`h-4.5 w-4.5 shrink-0 transition-colors ${
                              isActive
                                ? 'text-white'
                                : 'text-body dark:text-bodydark group-hover:text-primary dark:group-hover:text-secondary'
                            }`}
                          />
                          <span className="truncate flex-1">{item.name}</span>
                          {item.badgeCount > 0 && (
                            <span
                              title={item.badgeTitle}
                              aria-label={item.badgeTitle}
                              className={`ml-auto inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none tabular-nums ${
                                isActive
                                  ? 'bg-red-500 text-white ring-1 ring-white/50 shadow-xs'
                                  : 'bg-red-500 text-white shadow-xs'
                              }`}
                            >
                              {item.badgeCount}
                            </span>
                          )}
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
    </>
  );
};

export default Sidebar;
