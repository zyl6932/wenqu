import React, { useEffect, useRef } from 'react';
import { escHtml } from '../../utils/grouping';

export default function SearchHistoryDropdown({ items, onSelect }) {
  const ref = useRef(null);

  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) onSelect(null);
    }
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [onSelect]);

  if (!items || !items.length) return null;

  return (
    <div ref={ref} style={{
      position: 'absolute', bottom: '100%', left: 0, right: 0,
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 8, marginBottom: 4, maxHeight: 200, overflowY: 'auto',
      zIndex: 10, boxShadow: 'var(--shadow-lg)',
    }}>
      {items.slice(0, 8).map((q, i) => (
        <div key={i} style={{
          padding: '8px 12px', cursor: 'pointer', fontSize: 13,
          color: 'var(--ink-soft)', transition: 'background .1s',
        }}
          onMouseOver={(e) => e.target.style.background = 'var(--surface-hover)'}
          onMouseOut={(e) => e.target.style.background = ''}
          onClick={() => onSelect(q)}
        >
          {escHtml(q)}
        </div>
      ))}
    </div>
  );
}
