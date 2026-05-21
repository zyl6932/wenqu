import React from 'react';

export default function SidebarHeader({ onSearchToggle, onCollapseToggle }) {
  return (
    <div className="sidebar-header">
      <h1>问渠</h1>
      <div style={{ display: 'flex', gap: 4 }}>
        <button className="sidebar-btn" onClick={onSearchToggle} title="搜索">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </button>
        <button className="sidebar-btn btn-toggle-sidebar" onClick={onCollapseToggle} title="收起侧边栏">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
      </div>
    </div>
  );
}
