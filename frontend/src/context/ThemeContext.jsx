import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const ThemeContext = createContext(null);

function getStored(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => getStored('wenqu_theme', 'light'));
  const [fontSize, setFontSize] = useState(() => parseInt(getStored('wenqu_fontsize', '14')));

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty('--font-size', fontSize + 'px');
  }, [fontSize]);

  const toggleTheme = useCallback(() => {
    const html = document.documentElement;
    html.classList.add('theme-transition');
    setTheme(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('wenqu_theme', next);
      return next;
    });
    setTimeout(() => html.classList.remove('theme-transition'), 350);
  }, []);

  const changeFontSize = useCallback((delta) => {
    setFontSize(prev => {
      const next = Math.max(12, Math.min(20, prev + delta));
      localStorage.setItem('wenqu_fontsize', next);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, fontSize, toggleTheme, changeFontSize }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
