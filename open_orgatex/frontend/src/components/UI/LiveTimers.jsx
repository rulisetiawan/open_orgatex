import React, { useState, useEffect } from 'react';

function parseStartMs(startTimeStr) {
  if (!startTimeStr) return NaN;
  const str = String(startTimeStr).trim();
  if (str.includes(' ') || str.includes('T')) {
    return new Date(str.replace(' ', 'T')).getTime();
  }
  const parts = str.split(':').map(Number);
  const d = new Date();
  d.setHours(parts[0] || 0, parts[1] || 0, parts[2] || 0, 0);
  return d.getTime();
}

export function formatElapsedDuration(startTimeStr, nowMs = Date.now()) {
  if (!startTimeStr) return null;
  try {
    const startMs = parseStartMs(startTimeStr);
    if (isNaN(startMs)) return null;
    const diffSec = Math.max(0, Math.floor((nowMs - startMs) / 1000));
    if (diffSec > 86400) return null;
    if (diffSec < 60) return `${diffSec} dtk`;
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    if (mins < 60) {
      return secs > 0 ? `${mins} mnt ${secs} dtk` : `${mins} mnt`;
    }
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hrs} jam ${remMins} mnt`;
  } catch {
    return null;
  }
}

export function computeLiveRemaining(startTimeStr, targetMin, nowMs = Date.now()) {
  if (!startTimeStr || !targetMin) return null;
  try {
    const startMs = parseStartMs(startTimeStr);
    if (isNaN(startMs)) return null;
    const elapsedSec = Math.max(0, Math.floor((nowMs - startMs) / 1000));
    const targetSec = Number(targetMin) * 60;
    if (elapsedSec > targetSec + 30) {
      const overMin = Math.floor((elapsedSec - targetSec) / 60);
      return { isOvertime: true, text: `⚠️ Molor +${overMin} mnt` };
    }
    const remSec = targetSec - elapsedSec;
    const remMin = Math.max(0, Math.ceil(remSec / 60));
    return { isOvertime: false, text: `⏱ Sisa ~${remMin} mnt` };
  } catch {
    return null;
  }
}

/**
 * Isolated 1-second ticking elapsed duration display so parent pages
 * (like 3,191-line Logs.jsx) don't re-render every second.
 */
export function LiveElapsedText({ startTime, fallback = '-', prefix = '', suffix = '', className = '' }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!startTime) return;
    const id = setInterval(() => {
      if (!document.hidden) setNow(Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [startTime]);

  const text = formatElapsedDuration(startTime, now);
  if (!text) return fallback ? <span className={className}>{fallback}</span> : null;
  return (
    <span className={className}>
      {prefix}
      {text}
      {suffix}
    </span>
  );
}

export function LiveRemainingBadge({ startTime, targetMin, className = '' }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!startTime || !targetMin) return;
    const id = setInterval(() => {
      if (!document.hidden) setNow(Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [startTime, targetMin]);

  const info = computeLiveRemaining(startTime, targetMin, now);
  if (!info) return null;
  return (
    <span
      className={`${className} ${
        info.isOvertime
          ? 'text-rose-600 dark:text-rose-400 font-bold'
          : 'text-emerald-600 dark:text-emerald-400 font-semibold'
      }`}
    >
      {info.text}
    </span>
  );
}
