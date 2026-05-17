import React from 'react';

export default function ChunkToolbar({ selectedCount, total, onMerge, onRechunk }) {
  return (
    <div className="chunk-toolbar">
      <button onClick={onMerge} disabled={selectedCount < 2}>合并选中</button>
      <button onClick={onRechunk}>重新分块</button>
      <span className="chunk-count">{total} 块</span>
    </div>
  );
}
