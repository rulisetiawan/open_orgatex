import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, ArrowLeft } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-[65vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-2xl border border-stroke dark:border-strokedark bg-white dark:bg-boxdark p-8 shadow-sm text-center space-y-4">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-primary/10 text-primary dark:text-secondary flex items-center justify-center">
          <Compass className="h-7 w-7" />
        </div>
        <div>
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-primary dark:text-secondary">
            Error 404
          </p>
          <h2 className="mt-1 text-xl font-extrabold text-black dark:text-white">
            Halaman Tidak Ditemukan
          </h2>
          <p className="mt-1.5 text-xs text-body dark:text-bodydark">
            Rute yang Anda buka tidak tersedia pada aplikasi SMM Digital Automation.
          </p>
        </div>
        <div className="pt-2">
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold bg-primary text-white hover:bg-primary/90 shadow-sm transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Kembali ke Process Picture
          </Link>
        </div>
      </div>
    </div>
  );
}
