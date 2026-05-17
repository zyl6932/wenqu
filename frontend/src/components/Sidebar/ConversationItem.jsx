import React from 'react';
import { escHtml } from '../../utils/grouping';

export default function ConversationItem({ conv, isActive, onSelect, onRename, onDelete }) {
  return (
    <div className={`conv-item${isActive ? ' active' : ''}`} onClick={() => onSelect(conv.id)}>
      <span className="conv-item-title" onDoubleClick={(e) => { e.stopPropagation(); onRename(conv.id); }}>{escHtml(conv.title)}</span>
      <button className="conv-item-del" title="删除" onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}>&times;</button>
    </div>
  );
}
