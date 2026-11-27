import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DefaultLayout from './layout/DefaultLayout';
import ErrorBoundary from './components/UI/ErrorBoundary';
import NotFound from './components/UI/NotFound';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Machines = lazy(() => import('./pages/Machines'));
const Recipes = lazy(() => import('./pages/Recipes'));
const Programs = lazy(() => import('./pages/Programs'));
const Formulas = lazy(() => import('./pages/Formulas'));
const KanbanView = lazy(() => import('./pages/Planning/KanbanView'));
const CalendarView = lazy(() => import('./pages/Planning/CalendarView'));
const BatchListView = lazy(() => import('./pages/Planning/BatchListView'));
const FtpManager = lazy(() => import('./pages/Ftp/FtpManager'));
const FtpHealthMonitor = lazy(() => import('./pages/Ftp/FtpHealthMonitor'));
const Logs = lazy(() => import('./pages/Logs'));
const Alarms = lazy(() => import('./pages/Alarms'));
const TagMapping = lazy(() => import('./pages/TagMapping'));

function PageLoader() {
  return (
    <div className="space-y-4 animate-pulse py-4" role="status" aria-label="Memuat halaman">
      <div className="h-7 w-56 rounded-lg bg-gray-200 dark:bg-meta-4/60" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-gray-200/80 dark:bg-meta-4/50" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-gray-200/70 dark:bg-meta-4/40" />
    </div>
  );
}

function App() {
  return (
    <Router>
      <DefaultLayout>
        <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/process-analyser" element={<Logs />} />
              <Route path="/batch-history" element={<Logs defaultTab="archive" />} />
              <Route path="/logs" element={<Navigate to="/process-analyser" replace />} />
              <Route path="/machines" element={<Machines />} />
              <Route path="/tag-mapping" element={<TagMapping />} />
              <Route path="/recipes" element={<Recipes />} />
              <Route path="/programs" element={<Programs />} />
              <Route path="/formulas" element={<Formulas />} />
              {/* Sementara dialihkan ke /programs agar tidak bingung */}
              <Route path="/programs-edx" element={<Navigate to="/programs" replace />} />
              <Route path="/planning" element={<Navigate to="/planning/list" replace />} />
              <Route path="/planning/list" element={<BatchListView />} />
              <Route path="/planning/kanban" element={<KanbanView />} />
              <Route path="/planning/calendar" element={<CalendarView />} />
              <Route path="/ftp" element={<FtpManager />} />
              <Route path="/ftp-monitor" element={<FtpHealthMonitor />} />
              <Route path="/alarms" element={<Alarms />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </DefaultLayout>
    </Router>
  );
}

export default App;
