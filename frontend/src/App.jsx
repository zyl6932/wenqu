import React, { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar/Sidebar';
import ChatArea from './components/Chat/ChatArea';
import DocModal from './components/Modals/DocModal';
import ChunkModal from './components/Modals/ChunkModal';
import ToastContainer from './components/shared/ToastContainer';
import { useConversation } from './context/ConversationContext';
import { useToast } from './context/ToastContext';
import { useKeyboard } from './hooks/useKeyboard';
import { useDragDrop } from './hooks/useDragDrop';

export default function App() {
  const [docPath, setDocPath] = useState(null);
  const [chunkSource, setChunkSource] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('wenqu_sidebar_collapsed') !== 'false'
  );
  const { dispatch } = useConversation();
  const { addToast } = useToast();
  const inputRef = useRef(null);

  // 鼠标跟随光晕效果
  useEffect(() => {
    const onMove = (e) => {
      document.documentElement.style.setProperty('--mouse-x', (e.clientX / window.innerWidth * 100) + '%');
      document.documentElement.style.setProperty('--mouse-y', (e.clientY / window.innerHeight * 100) + '%');
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  const closeAll = useCallback(() => {
    setDocPath(null);
    setChunkSource(null);
  }, []);

  useKeyboard({
    onEscape: closeAll,
    onCtrlK: () => {
      const el = document.querySelector('.input-wrapper textarea');
      if (el) el.focus();
    },
    onCtrlN: () => dispatch({ type: 'NEW' }),
  });

  useDragDrop((msg) => {
    addToast(msg || '上传完成', msg === '上传失败' ? 'error' : 'success');
    // trigger doc list refresh - the DocSection component handles this via its own state
  });

  // Sidebar collapse state listener
  useEffect(() => {
    function handleResize() {
      if (window.innerWidth > 768) {
        const collapsed = localStorage.getItem('wenqu_sidebar_collapsed') === 'true';
        setSidebarCollapsed(collapsed);
      }
    }
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <>
      <ToastContainer />
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => {
          const next = !sidebarCollapsed;
          localStorage.setItem('wenqu_sidebar_collapsed', String(next));
          setSidebarCollapsed(next);
        }}
        onOpenChunks={setChunkSource}
      />
      <button
        id="btn-expand-sidebar"
        onClick={() => {
          localStorage.setItem('wenqu_sidebar_collapsed', 'false');
          setSidebarCollapsed(false);
        }}
        style={{
          display: sidebarCollapsed ? 'flex' : 'none',
          position: 'fixed', left: 8, top: 15, zIndex: 60,
          width: 32, height: 32, border: '1px solid var(--border)',
          borderRadius: 8, background: 'var(--surface)',
          color: 'var(--ink-soft)', cursor: 'pointer',
          boxShadow: 'var(--shadow)', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <ChatArea sidebarCollapsed={sidebarCollapsed} />
      {docPath && <DocModal path={docPath} onClose={() => setDocPath(null)} />}
      {chunkSource && <ChunkModal source={chunkSource} onClose={() => setChunkSource(null)} />}
    </>
  );
}
