import { useEffect } from 'react';

export function useKeyboard(handlers) {
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') handlers.onEscape?.();
      if (e.ctrlKey && e.key === 'k') { e.preventDefault(); if (window.innerWidth > 768) handlers.onCtrlK?.(); }
      if (e.ctrlKey && e.key === 'n') { e.preventDefault(); if (window.innerWidth > 768) handlers.onCtrlN?.(); }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [handlers]);
}
