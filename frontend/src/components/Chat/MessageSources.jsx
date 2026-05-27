import React from 'react';
import { escHtml } from '../../utils/grouping';

export default function MessageSources({ sources }) {
  if (!sources || !sources.length) return null;
  return (
    <div className="message-sources">
      引用: {sources.map((s, i) => {
        const name = typeof s === 'string' ? s : s.name;
        const score = typeof s === 'string' ? null : s.score;
        return <span key={i}>{escHtml(name)}{score != null && <em style={{fontSize:10,color:'var(--ink-mute)',marginLeft:2}}>({(score * 100).toFixed(0)}%)</em>}</span>;
      })}
    </div>
  );
}
