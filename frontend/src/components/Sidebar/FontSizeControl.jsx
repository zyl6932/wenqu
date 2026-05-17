import React from 'react';
import { useTheme } from '../../context/ThemeContext';

export default function FontSizeControl() {
  const { fontSize, changeFontSize } = useTheme();
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      <button className="sidebar-btn" onClick={() => changeFontSize(-1)}>A-</button>
      <span style={{ fontSize: 11, color: 'var(--ink-mute)', minWidth: 20, textAlign: 'center' }}>{fontSize}</span>
      <button className="sidebar-btn" onClick={() => changeFontSize(1)}>A+</button>
    </div>
  );
}
