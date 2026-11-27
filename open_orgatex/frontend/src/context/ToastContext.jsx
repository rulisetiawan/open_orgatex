import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

let toastSeq = 0;

const VARIANT_STYLES = {
  success: {
    container: 'bg-emerald-50/95 dark:bg-emerald-950/95 border-emerald-300 dark:border-emerald-700 text-emerald-900 dark:text-emerald-100',
    icon: CheckCircle2,
    iconColor: 'text-emerald-600 dark:text-emerald-400',
  },
  error: {
    container: 'bg-rose-50/95 dark:bg-rose-950/95 border-rose-300 dark:border-rose-700 text-rose-900 dark:text-rose-100',
    icon: AlertCircle,
    iconColor: 'text-rose-600 dark:text-rose-400',
  },
  warning: {
    container: 'bg-amber-50/95 dark:bg-amber-950/95 border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-100',
    icon: AlertTriangle,
    iconColor: 'text-amber-600 dark:text-amber-400',
  },
  info: {
    container: 'bg-white/95 dark:bg-boxdark/95 border-primary/40 dark:border-primary/50 text-black dark:text-white',
    icon: Info,
    iconColor: 'text-primary dark:text-secondary',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef(new Map());

  // Native <dialog> confirmation state
  const [confirmState, setConfirmState] = useState(null);
  const dialogRef = useRef(null);

  const dismiss = useCallback((id) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (message, options = {}) => {
      const {
        type = 'info',
        title = null,
        duration = type === 'error' ? 6000 : 4500,
      } = typeof options === 'string' ? { type: options } : options;

      const id = ++toastSeq;
      setToasts((prev) => [...prev.slice(-4), { id, type, title, message: String(message ?? '') }]);

      if (duration > 0) {
        const timer = setTimeout(() => {
          dismiss(id);
        }, duration);
        timersRef.current.set(id, timer);
      }
      return id;
    },
    [dismiss]
  );

  const toast = useCallback(
    Object.assign(
      (msg, opts) => notify(msg, opts),
      {
        success: (msg, opts = {}) => notify(msg, { ...opts, type: 'success' }),
        error: (msg, opts = {}) => notify(msg, { ...opts, type: 'error' }),
        warning: (msg, opts = {}) => notify(msg, { ...opts, type: 'warning' }),
        info: (msg, opts = {}) => notify(msg, { ...opts, type: 'info' }),
        dismiss,
      }
    ),
    [notify, dismiss]
  );

  const confirm = useCallback((message, options = {}) => {
    return new Promise((resolve) => {
      setConfirmState({
        message: String(message ?? ''),
        title: options.title || 'Konfirmasi Tindakan',
        confirmText: options.confirmText || 'Ya, Lanjutkan',
        cancelText: options.cancelText || 'Batal',
        danger: Boolean(options.danger),
        resolve,
      });
    });
  }, []);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (confirmState) {
      if (!dlg.open) dlg.showModal();
    } else if (dlg.open) {
      dlg.close();
    }
  }, [confirmState]);

  const handleConfirmClose = (result) => {
    if (confirmState?.resolve) {
      confirmState.resolve(result);
    }
    setConfirmState(null);
  };

  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
      timersRef.current.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toast, confirm, dismiss }}>
      {children}

      {/* Global Toast Viewport (Top-right, non-blocking, accessible) */}
      <div
        role="region"
        aria-label="Notifikasi"
        aria-live="polite"
        className="fixed top-4 right-4 z-[100000] flex flex-col gap-2.5 w-full max-w-sm pointer-events-none px-4 sm:px-0"
      >
        {toasts.map((t) => {
          const style = VARIANT_STYLES[t.type] || VARIANT_STYLES.info;
          const Icon = style.icon;
          return (
            <div
              key={t.id}
              role={t.type === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto rounded-xl border shadow-lg backdrop-blur-md p-3.5 flex items-start gap-3 text-xs animate-in fade-in slide-in-from-top-2 duration-200 ${style.container}`}
            >
              <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${style.iconColor}`} />
              <div className="flex-1 min-w-0">
                {t.title && <p className="font-bold mb-0.5">{t.title}</p>}
                <p className="whitespace-pre-line break-words leading-relaxed">{t.message}</p>
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Tutup notifikasi"
                className="p-1 rounded-md opacity-70 hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10 transition shrink-0"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Native <dialog> Top-Layer Confirm Modal */}
      <dialog
        ref={dialogRef}
        onCancel={(e) => {
          e.preventDefault();
          handleConfirmClose(false);
        }}
        onClick={(e) => {
          if (e.target === dialogRef.current) {
            handleConfirmClose(false);
          }
        }}
        className="m-auto w-full max-w-md rounded-2xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark p-0 text-black dark:text-white shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-sm"
      >
        {confirmState && (
          <div className="p-5 space-y-4">
            <div className="flex items-start gap-3">
              <div
                className={`p-2 rounded-xl shrink-0 ${
                  confirmState.danger
                    ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                    : 'bg-primary/10 text-primary dark:text-secondary'
                }`}
              >
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold text-black dark:text-white">{confirmState.title}</h3>
                <p className="mt-1.5 text-xs text-body dark:text-bodydark whitespace-pre-line leading-relaxed">
                  {confirmState.message}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-stroke dark:border-strokedark">
              <button
                type="button"
                onClick={() => handleConfirmClose(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold border border-stroke dark:border-strokedark bg-gray hover:bg-gray-200 dark:bg-meta-4 dark:hover:bg-meta-4/80 text-black dark:text-white transition"
              >
                {confirmState.cancelText}
              </button>
              <button
                type="button"
                autoFocus
                onClick={() => handleConfirmClose(true)}
                className={`px-4 py-2 rounded-lg text-xs font-bold text-white shadow-sm transition ${
                  confirmState.danger
                    ? 'bg-rose-600 hover:bg-rose-700'
                    : 'bg-primary hover:bg-primary/90'
                }`}
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
