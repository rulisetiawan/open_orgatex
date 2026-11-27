import { useEffect, useRef } from 'react';

/**
 * Runs a polling callback at `delayMs` intervals, automatically pausing when
 * the browser tab is hidden (Page Visibility API) and immediately refreshing
 * when the tab becomes visible again.
 */
export function useVisibilityInterval(callback, delayMs, enabled = true) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled || !delayMs || delayMs <= 0) return;

    let intervalId = null;

    const tick = () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      savedCallback.current?.();
    };

    const start = () => {
      if (intervalId) clearInterval(intervalId);
      intervalId = setInterval(tick, delayMs);
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        savedCallback.current?.();
        start();
      } else if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    start();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (intervalId) clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [delayMs, enabled]);
}

export default useVisibilityInterval;
