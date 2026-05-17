import React, { useState } from 'react';

export default function ChunkItem({ chunk, index, checked, onCheck, onEdit, onSplit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [splitting, setSplitting] = useState(false);
  const [editText, setEditText] = useState(chunk.text);
  const [splitSep, setSplitSep] = useState('');

  let cls = 'chunk-item';
  if (editing) cls += ' editing';
  if (splitting) cls += ' splitting';

  const preview = chunk.text.length > 200 ? chunk.text.slice(0, 200) + '...' : chunk.text;

  return (
    <div className={cls}>
      <div className="chunk-head">
        <input type="checkbox" checked={checked} onChange={e => onCheck(chunk.id, e.target.checked)} />
        <span className="chunk-idx">#{index + 1}</span>
        <span className="chunk-tokens">{chunk.tokens} tok</span>
        <div className="chunk-actions">
          <button onClick={() => { setEditing(true); setSplitting(false); }}>编辑</button>
          <button onClick={() => { setSplitting(true); setEditing(false); }}>拆分</button>
          <button className="btn-del" onClick={() => onDelete(chunk.id)}>删除</button>
        </div>
      </div>
      <div className="chunk-preview">{preview}</div>
      <div className="chunk-ta">
        <textarea value={editText} onChange={e => setEditText(e.target.value)} />
        <div className="edit-actions">
          <button className="btn-cancel" onClick={() => { setEditing(false); setEditText(chunk.text); }}>取消</button>
          <button className="btn-save" onClick={() => { onEdit(chunk.id, editText); setEditing(false); }}>保存</button>
        </div>
      </div>
      <div className="chunk-split-ta">
        <input type="text" value={splitSep} onChange={e => setSplitSep(e.target.value)} placeholder="输入分隔文本" />
        <div className="edit-actions">
          <button className="btn-cancel" onClick={() => { setSplitting(false); setSplitSep(''); }}>取消</button>
          <button className="btn-save" onClick={() => { onSplit(chunk.id, splitSep); setSplitting(false); setSplitSep(''); }}>拆分</button>
        </div>
      </div>
    </div>
  );
}
