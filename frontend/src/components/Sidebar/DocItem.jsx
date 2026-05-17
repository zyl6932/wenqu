import React from 'react';
import { escHtml } from '../../utils/grouping';

function iconForFile(name) {
  if (name.endsWith('.txt')) return 'T';
  if (name.endsWith('.md')) return 'M';
  if (name.endsWith('.docx')) return 'D';
  if (name.endsWith('.pdf')) return 'P';
  if (name.endsWith('.pptx')) return 'S';
  return '·';
}

export default function DocItem({ doc, onOpen, onDelete }) {
  return (
    <div className="doc-item">
      <span className="doc-icon">{iconForFile(doc.name)}</span>
      <span className="doc-name" title={escHtml(doc.name)} onClick={() => onOpen(doc.path)}>{escHtml(doc.name)}</span>
      <button className="doc-item-del" title="删除" onClick={(e) => onDelete(doc.path, e)}>&times;</button>
    </div>
  );
}
