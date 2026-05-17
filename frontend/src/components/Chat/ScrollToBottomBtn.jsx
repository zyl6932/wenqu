import React from 'react';

export default function ScrollToBottomBtn({ visible, onClick }) {
  if (!visible) return null;
  return (
    <button onClick={onClick} style={{
      display: 'block', position: 'sticky', bottom: 16, float: 'right', zIndex: 5,
      padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 16,
      background: 'var(--surface)', color: 'var(--ink-soft)', cursor: 'pointer',
      boxShadow: 'var(--shadow)',
    }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>
  );
}
