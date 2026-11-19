import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DefaultLayout from './layout/DefaultLayout';
import Dashboard from './pages/Dashboard';
import Machines from './pages/Machines';
import Recipes from './pages/Recipes';
import Programs from './pages/Programs';
import OrgatexEdxProgram from './pages/OrgatexEdxProgram';
import KanbanView from './pages/Planning/KanbanView';
import CalendarView from './pages/Planning/CalendarView';
import BatchListView from './pages/Planning/BatchListView';
import FtpManager from './pages/Ftp/FtpManager';
import Logs from './pages/Logs';

function App() {
  return (
    <Router>
      <DefaultLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/process-analyser" element={<Logs />} />
          <Route path="/logs" element={<Navigate to="/process-analyser" replace />} />
          <Route path="/machines" element={<Machines />} />
          <Route path="/recipes" element={<Recipes />} />
          <Route path="/programs" element={<Programs />} />
          {/* Sementara dialihkan ke /programs agar tidak bingung */}
          <Route path="/programs-edx" element={<Navigate to="/programs" replace />} />
          <Route path="/planning" element={<Navigate to="/planning/list" replace />} />
          <Route path="/planning/list" element={<BatchListView />} />
          <Route path="/planning/kanban" element={<KanbanView />} />
          <Route path="/planning/calendar" element={<CalendarView />} />
          <Route path="/ftp" element={<FtpManager />} />
          <Route path="/alarms" element={<Logs />} />
        </Routes>
      </DefaultLayout>
    </Router>
  );
}

export default App;
