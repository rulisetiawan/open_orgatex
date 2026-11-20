import React, { useState } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import { useTheme } from '../context/ThemeContext';

const DefaultLayout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="bg-whiten dark:bg-boxdark-2 text-body dark:text-bodydark min-h-screen transition-colors duration-200">
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

          {/* Main Content with smooth page entry animation */}
          <main className="page-enter flex-1">
            <div className="mx-auto max-w-screen-2xl p-4 md:p-6 2xl:p-10">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default DefaultLayout;
