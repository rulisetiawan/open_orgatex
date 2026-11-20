import React, { useState, useEffect } from 'react';
import { Menu, Sun, Moon, Clock, ShieldCheck } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const Header = ({ sidebarOpen, setSidebarOpen, darkMode, setDarkMode }) => {
  const { theme, toggleTheme } = useTheme();
  const [clock, setClock] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setClock(now.toLocaleTimeString('id-ID', { hour12: false }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const shiftInfo = (() => {
    const hours = new Date().getHours();
    if (hours >= 6 && hours < 14) return { label: 'Shift 1', time: '06:00 - 14:00' };
    if (hours >= 14 && hours < 22) return { label: 'Shift 2', time: '14:00 - 22:00' };
    return { label: 'Shift 3', time: '22:00 - 06:00' };
  })();

  const isDark = darkMode !== undefined ? darkMode : theme === 'dark';
  const handleToggle = setDarkMode ? () => setDarkMode(!darkMode) : toggleTheme;

  return (
    <header className="sticky top-0 z-999 flex w-full border-b border-stroke bg-white/95 backdrop-blur shadow-sm dark:border-strokedark dark:bg-boxdark/95 transition-colors duration-200">
      <div className="flex flex-grow items-center justify-between px-4 py-3 md:px-6 2xl:px-10">
        <div className="flex items-center gap-3 sm:gap-4">
          {/* Hamburger Toggle for Mobile */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="z-99999 block rounded-lg border border-stroke bg-white p-2 shadow-sm dark:border-strokedark dark:bg-meta-4 lg:hidden hover:border-primary transition-colors"
            aria-label="Toggle Navigation"
          >
            <Menu className="h-5 w-5 text-black dark:text-white" />
          </button>

          {/* Real-time Status Badge */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-semibold">Online</span>
          </div>
        </div>

        {/* Center / Right: Shift, Clock, Dark/Light Mode, User Profile */}
        <div className="flex items-center gap-3 sm:gap-6">
          {/* Shift & Real-time Clock */}
          <div className="hidden md:flex items-center gap-3 border-r border-stroke dark:border-strokedark pr-5">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray dark:bg-meta-4 text-xs font-semibold text-black dark:text-white">
              <Clock className="w-3.5 h-3.5 text-primary" />
              <span className="font-mono tabular-nums">{clock || '--:--:--'}</span>
            </div>
            <div className="text-xs font-medium text-body dark:text-bodydark flex items-center gap-1.5">
              <span className="font-semibold text-black dark:text-white">{shiftInfo.label}</span>
              <span className="text-gray-400">({shiftInfo.time})</span>
            </div>
          </div>

          {/* Theme Switcher Toggle (Sun / Moon) */}
          <button
            onClick={handleToggle}
            type="button"
            className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-stroke bg-gray hover:bg-gray-2 hover:text-primary dark:border-strokedark dark:bg-meta-4 dark:text-white dark:hover:bg-slate-800 transition-all shadow-sm cursor-pointer"
            aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            title={isDark ? "Mode Terang" : "Mode Gelap"}
          >
            {isDark ? (
              <Sun className="h-4 w-4 text-amber-400 transition-transform hover:rotate-45" />
            ) : (
              <Moon className="h-4 w-4 text-slate-700 transition-transform hover:-rotate-12" />
            )}
          </button>

          {/* User Profile Info */}
          <div className="flex items-center gap-2.5 pl-2">
            <div className="hidden text-right lg:block">
              <span className="block text-xs font-bold text-black dark:text-bodydark1">
                Operator
              </span>
            </div>
            <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 text-primary dark:bg-primary/20 dark:text-secondary flex items-center justify-center font-bold text-xs shadow-xs">
              OP
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
