import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';
import { useTheme } from '../context/ThemeContext';

const DefaultLayout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();

  return (
    <div className="bg-whiten dark:bg-boxdark-2 text-body dark:text-bodydark min-h-screen transition-colors duration-200">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100001] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-primary focus:text-white focus:text-xs focus:font-bold focus:shadow-lg"
      >
        Langsung ke konten utama
      </a>

      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

        {/* Content Area */}
        <div className="relative flex flex-1 flex-col overflow-y-auto overflow-x-hidden">
          {/* Header */}
          <Header
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            darkMode={theme === 'dark'}
            setDarkMode={toggleTheme}
          />

          {/* Main Content with smooth page entry animation on route change */}
          <main id="main-content" key={location.pathname} className="page-enter flex-1">
            <div className="w-full p-4 md:p-6 2xl:p-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default DefaultLayout;
