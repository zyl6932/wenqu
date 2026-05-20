import React, { useState, useEffect, useCallback } from 'react';
import { fetchDocs, deleteDoc, importDocs } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import DocItemView from './DocItem';

export default function DocSection({ onOpenChunks }) {
  const [docs, setDocs] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const [importing, setImporting] = useState(false);
  const { addToast } = useToast();

  const loadDocs = useCallback(async () => {
    try {
      const data = await fetchDocs();
      setDocs(data.docs || []);
    } catch { setDocs([]); }
  }, []);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  async function handleDelete(path, e) {
    e.stopPropagation();
    if (!confirm('确定删除此文档？')) return;
    try {
      await deleteDoc(path);
      loadDocs();
    } catch { addToast('删除失败', 'error'); }
  }

  async function handleImport() {
    setImporting(true);
    try {
      const data = await importDocs();
      addToast(data.message || '导入完成');
      loadDocs();
    } catch { addToast('导入失败', 'error'); }
    finally { setImporting(false); }
  }

  return (
    <div className="doc-section">
      <div className="doc-section-header" onClick={() => setCollapsed(!collapsed)}>
        <h3>已导入文档 <span style={{ float: 'right', fontWeight: 400 }}>{docs.length}</span></h3>
        <span style={{ transform: collapsed ? 'rotate(-90deg)' : '', transition: 'transform .2s', fontSize: 10 }}>▼</span>
      </div>
      {!collapsed && (
        <>
          <div className="doc-list-wrap">
            {docs.length === 0
              ? <div className="empty-docs">暂无文档</div>
              : docs.map(d => (
                  <DocItemView key={d.path} doc={d} onOpen={() => onOpenChunks(d.path)} onDelete={handleDelete} />
                ))
            }
          </div>
          <button className="btn-import" onClick={handleImport} disabled={importing}>
            {importing ? '导入中...' : '+ 导入文档'}
          </button>
        </>
      )}
    </div>
  );
}
