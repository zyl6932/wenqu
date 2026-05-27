import React, { useState, useEffect, useCallback } from 'react';
import Modal from './Modal';
import ChunkToolbar from './ChunkToolbar';
import ChunkItem from './ChunkItem';
import { fetchChunks, updateChunk, deleteOneChunk, deleteChunks, splitChunk, mergeChunks, importDocs } from '../../api/client';
import { useToast } from '../../context/ToastContext';

export default function ChunkModal({ source, onClose }) {
  const [chunks, setChunks] = useState(null);
  const [checkedIds, setCheckedIds] = useState(new Set());
  const { addToast } = useToast();

  const load = useCallback(async () => {
    try {
      const data = await fetchChunks(source);
      setChunks(data.chunks || []);
    } catch { setChunks([]); }
  }, [source]);

  useEffect(() => {
    if (!source) return;
    let cancelled = false;
    fetchChunks(source).then(data => {
      if (!cancelled) setChunks(data.chunks || []);
    }).catch(() => { if (!cancelled) setChunks([]); });
    return () => { cancelled = true; };
  }, [source]);

  const title = source ? `块编辑 - ${source.split(/[/\\]/).pop()} (${chunks?.length || 0} 块)` : '块编辑器';

  function toggleCheck(id, on) {
    setCheckedIds(prev => { const next = new Set(prev); on ? next.add(id) : next.delete(id); return next; });
  }

  async function handleEdit(id, text) {
    if (!text.trim()) { addToast('文本不能为空', 'error'); return; }
    try {
      await updateChunk(id, text);
      load();
    } catch { addToast('保存失败', 'error'); }
  }

  async function handleSplit(id, sep) {
    if (!sep) { addToast('请输入分隔文本', 'error'); return; }
    try {
      await splitChunk(id, sep);
      load();
    } catch { addToast('拆分失败', 'error'); }
  }

  async function handleDeleteSingle(id) {
    if (!confirm('确定删除此块？')) return;
    try {
      await deleteOneChunk(id);
      load();
    } catch { addToast('删除失败', 'error'); }
  }

  async function handleMerge() {
    if (checkedIds.size < 2) { addToast('请至少勾选两块', 'error'); return; }
    if (!confirm(`合并 ${checkedIds.size} 块？`)) return;
    try {
      await mergeChunks([...checkedIds]);
      setCheckedIds(new Set());
      load();
    } catch { addToast('合并失败', 'error'); }
  }

  async function handleRechunk() {
    if (!confirm('重新分块将清除所有现有块，确定？')) return;
    try {
      const data = await fetchChunks(source, 1, 10000);
      if (data.chunks?.length) await deleteChunks(data.chunks.map(c => c.id));
      const imp = await importDocs();
      addToast(imp.message || '完成');
      load();
    } catch { addToast('失败', 'error'); }
  }

  if (chunks === null) return null;

  return (
    <Modal title={title} onClose={onClose} maxWidth={860}>
      {chunks.length === 0 ? (
        <div className="modal-loading">暂无向量块</div>
      ) : (
        <>
          <ChunkToolbar
            selectedCount={checkedIds.size}
            total={chunks.length}
            onMerge={handleMerge}
            onRechunk={handleRechunk}
          />
          <div className="chunk-list">
            {chunks.map((c, i) => (
              <ChunkItem
                key={c.id}
                chunk={c}
                index={i}
                checked={checkedIds.has(c.id)}
                onCheck={toggleCheck}
                onEdit={handleEdit}
                onSplit={handleSplit}
                onDelete={handleDeleteSingle}
              />
            ))}
          </div>
        </>
      )}
    </Modal>
  );
}
