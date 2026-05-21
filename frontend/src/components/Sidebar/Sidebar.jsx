import React, { useState, useRef, useEffect } from 'react';
import { useConversation } from '../../context/ConversationContext';
import SidebarHeader from './SidebarHeader';
import SearchPanel from './SearchPanel';
import ConversationList from './ConversationList';
import SettingsModal from './SettingsModal';

export default function Sidebar({ onOpenChunks, collapsed, onToggleCollapse }) {
  const [searchVisible, setSearchVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { state, dispatch } = useConversation();

  const sidebarRef = useRef(null);

  useEffect(() => {
    function onResize() {
      if (window.innerWidth > 768) {
        setMobileOpen(false);
        document.getElementById('sidebar-backdrop')?.classList.remove('open');
      }
    }
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  function handleCollapse() {
    if (window.innerWidth <= 768) {
      setMobileOpen(v => !v);
    } else {
      onToggleCollapse?.();
    }
  }

  const sidebarClass = [
    'sidebar',
    (!mobileOpen && collapsed) ? 'collapsed' : '',
    mobileOpen ? 'open' : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      <div id="sidebar-backdrop" className={`sidebar-backdrop${mobileOpen ? ' open' : ''}`} onClick={handleCollapse} />
      <button className="mobile-menu-btn" onClick={handleCollapse} style={{ display: mobileOpen ? 'none' : '' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <aside ref={sidebarRef} className={sidebarClass}>
        <SidebarHeader onSearchToggle={() => setSearchVisible(v => !v)} onCollapseToggle={handleCollapse} />
        <SearchPanel visible={searchVisible} value={state.filter || ''} onChange={filter => dispatch({ type: 'SET_FILTER', filter })} />
        <div style={{ padding: '4px 16px' }}>
          <button className="sidebar-btn" onClick={() => dispatch({ type: 'NEW' })} style={{ width: '100%', fontSize: 13, padding: '8px 0' }}>+ 新建对话</button>
        </div>
        <ConversationList />
        <div style={{ borderTop: '1px solid var(--border)' }}>
          <button
            className="sidebar-btn"
            onClick={() => setSettingsVisible(true)}
            style={{ width: '100%', border: 'none', borderRadius: 0, padding: 8, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-start', fontFamily: 'var(--serif)' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            设置
          </button>
          <SettingsModal visible={settingsVisible} onClose={() => setSettingsVisible(false)} onOpenChunks={onOpenChunks} />
        </div>
      </aside>
    </>
  );
}
