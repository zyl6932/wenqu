import React from 'react';
import ThemeToggle from './ThemeToggle';
import FontSizeControl from './FontSizeControl';
import ExportButton from './ExportButton';
import DocSection from './DocSection';

export default function SettingsPanel({ visible, onOpenChunks }) {
  if (!visible) return null;
  return (
    <div style={{ borderTop: '1px solid var(--border)' }}>
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--bg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>主题</span>
          <ThemeToggle />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>字号</span>
          <FontSizeControl />
        </div>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <ExportButton />
        </div>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <DocSection onOpenChunks={onOpenChunks} />
        </div>
      </div>
    </div>
  );
}
