import React from 'react';
import { Menu, Bell, Sun, Moon } from 'lucide-react';

const Header = ({ sidebarOpen, setSidebarOpen, darkMode, setDarkMode }) => {
  return (
    <header className="sticky top-0 z-999 flex w-full bg-white drop-shadow-1 dark:bg-boxdark dark:drop-shadow-none">
      <div className="flex flex-grow items-center justify-between px-4 py-4 shadow-2 md:px-6 2xl:px-11">
        <div className="flex items-center gap-2 sm:gap-4 lg:hidden">
          {/* Hamburger Toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="z-99999 block rounded-sm border border-stroke bg-white p-1.5 shadow-sm dark:border-strokedark dark:bg-boxdark lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>

        <div className="hidden sm:block">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-success animate-pulse"></span>
            <span className="text-xs font-semibold text-meta-3">SETEX 777 COMMUNICATION ENGINE ACTIVE</span>
          </div>
        </div>

        <div className="flex items-center gap-3 2xsm:gap-7">
          {/* Dark Mode Toggler */}
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="relative flex h-8.5 w-8.5 items-center justify-center rounded-full border-[0.5px] border-stroke bg-gray hover:text-primary dark:border-strokedark dark:bg-meta-4 dark:text-white"
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {/* User Profile Info */}
          <div className="flex items-center gap-4">
            <span className="hidden text-right lg:block">
              <span className="block text-sm font-medium text-black dark:text-white">Supervisor Celup</span>
              <span className="block text-xs text-body">Dyehouse Admin</span>
            </span>
            <div className="h-10 w-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">
              SC
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
