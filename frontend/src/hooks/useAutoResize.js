import { useCallback } from 'react';

export function useAutoResize() {
  return useCallback((el) => {
    if (!el) return;
    el.style.height = 'auto';
    const h = Math.min(el.scrollHeight, 120);
    el.style.height = h + 'px';
    el.style.overflowY = el.scrollHeight > 120 ? 'auto' : 'hidden';
  }, []);
}
