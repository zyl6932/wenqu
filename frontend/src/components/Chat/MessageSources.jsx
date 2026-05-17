import React from 'react';
import { escHtml } from '../../utils/grouping';

export default function MessageSources({ sources }) {
  if (!sources || !sources.length) return null;
  return (
    <div className="message-sources">
      引用: {sources.map((s, i) => <span key={i}>{escHtml(s)}</span>)}
    </div>
  );
}
