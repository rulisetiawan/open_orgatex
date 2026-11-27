import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('UI ErrorBoundary caught:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[60vh] flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-rose-500/30 bg-white dark:bg-boxdark p-6 shadow-lg text-center space-y-4">
            <div className="mx-auto w-12 h-12 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-black dark:text-white">
                Terjadi Kesalahan Tampilan
              </h2>
              <p className="text-xs text-body dark:text-bodydark mt-1">
                Halaman mengalami gangguan tak terduga. Data di server tetap aman.
              </p>
              {this.state.error?.message && (
                <pre className="mt-3 p-2.5 rounded-lg bg-gray dark:bg-meta-4/50 text-[11px] font-mono text-rose-600 dark:text-rose-400 overflow-x-auto text-left">
                  {this.state.error.message}
                </pre>
              )}
            </div>
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold bg-primary text-white hover:bg-primary/90 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Coba Muat Ulang
              </button>
              <a
                href="/"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold border border-stroke dark:border-strokedark bg-gray dark:bg-meta-4 text-black dark:text-white hover:bg-gray-200 dark:hover:bg-meta-4/80 transition"
              >
                <Home className="h-3.5 w-3.5" />
                Beranda
              </a>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
