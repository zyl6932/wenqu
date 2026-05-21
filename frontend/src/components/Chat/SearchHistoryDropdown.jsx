import React, { useEffect, useRef } from 'react';
import { escHtml } from '../../utils/grouping';
import { useConversation } from '../../context/ConversationContext';

const HISTORY_KEY = 'wenqu_search_history';

function removeItem(q) {
  try {
    let h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    h = h.filter(item => item !== q);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
  } catch {}
}

export default function SearchHistoryDropdown({ items, onSelect }) {
  const ref = useRef(null);
  const [, forceUpdate] = React.useState(0);

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
          display: 'flex', alignItems: 'center',
          padding: '8px 12px', cursor: 'pointer', fontSize: 13,
          color: 'var(--ink-soft)', transition: 'background .1s',
        }}
          onMouseOver={(e) => e.currentTarget.style.background = 'var(--surface-hover)'}
          onMouseOut={(e) => e.currentTarget.style.background = ''}
        >
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} onClick={() => onSelect(q)}>
            {escHtml(q)}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); removeItem(q); forceUpdate(n => n + 1); }}
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
        </div>
      ))}
    </div>
  );
}
