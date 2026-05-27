import React, { useRef } from 'react';
import { escHtml } from '../../utils/grouping';

const HISTORY_KEY = 'wenqu_search_history';

function removeItem(q) {
  try {
    let h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    h = h.filter(item => item !== q);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
  } catch {}
}

export default function SearchHistoryDropdown({ items, onSelect, hoverIndex, onHoverIndex, longPressMode }) {
  const ref = useRef(null);

  if (!items || !items.length) return null;

  return (
    <div ref={ref} className="history-dropdown" style={{
      position: 'absolute', bottom: '100%', left: 0, right: 0,
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 8, marginBottom: 4, maxHeight: 200, overflowY: 'auto',
      zIndex: 10, boxShadow: 'var(--shadow-lg)',
    }}>
      {items.slice(0, 8).map((q, i) => (
        <div key={i} data-hist-item style={{
          display: 'flex', alignItems: 'center', height: 36,
          padding: '8px 12px', cursor: 'pointer', fontSize: 13, boxSizing: 'border-box',
          color: 'var(--ink-soft)',
          background: hoverIndex === i ? 'var(--surface-hover)' : '',
        }}
          onMouseOver={() => onHoverIndex?.(i)}
          onMouseDown={(e) => { e.preventDefault(); onSelect(q); }}
        >
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {escHtml(q)}
          </span>
          {!longPressMode && (
            <button
              onClick={(e) => { e.stopPropagation(); removeItem(q); }}
              style={{
                marginLeft: 8, width: 18, height: 18, border: 'none', borderRadius: 3,
                background: 'transparent', color: 'var(--ink-mute)', cursor: 'pointer',
                fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, opacity: 0,
              }}
              className="history-item-del"
              onMouseOver={(e) => e.currentTarget.style.opacity = '1'}
              onMouseOut={(e) => e.currentTarget.style.opacity = '0'}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
