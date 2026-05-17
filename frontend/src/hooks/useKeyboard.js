import { useEffect } from 'react';

export function useKeyboard(handlers) {
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') handlers.onEscape?.();
      if (e.ctrlKey && e.key === 'k') { e.preventDefault(); handlers.onCtrlK?.(); }
      if (e.ctrlKey && e.key === 'n') { e.preventDefault(); handlers.onCtrlN?.(); }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [handlers]);
}
