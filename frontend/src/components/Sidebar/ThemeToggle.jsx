import React from 'react';
import { useTheme } from '../../context/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button className="sidebar-btn" onClick={toggleTheme} style={{ width: 'auto', padding: '4px 10px' }}>
      {theme === 'dark' ? '☀ 深色' : '☽ 浅色'}
    </button>
  );
}
