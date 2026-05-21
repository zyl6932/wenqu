import React, { useRef, useEffect } from 'react';

export default function SearchPanel({ visible, value, onChange }) {
  const inputRef = useRef(null);
  useEffect(() => {
    if (visible) setTimeout(() => inputRef.current?.focus(), 100);
  }, [visible]);

  if (!visible) return null;
  return (
    <div style={{ padding: '0 16px 8px' }}>
      <div style={{ position: 'relative' }}>
        <input
          ref={inputRef}
          type="text"
          placeholder="搜索对话..."
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ width: '100%', padding: '7px 24px 7px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, background: 'var(--bg)', color: 'var(--ink)', outline: 'none', fontFamily: 'var(--serif)' }}
        />
        {value && (
          <span onClick={() => onChange('')} style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--ink-mute)', fontSize: 12 }}>x</span>
        )}
      </div>
    </div>
  );
}
