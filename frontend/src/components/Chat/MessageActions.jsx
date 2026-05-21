import React, { useState } from 'react';
import { sendFeedback } from '../../api/client';

export default function MessageActions({ question, contexts, onRegenerate, onDelete }) {
  const [feedback, setFeedback] = useState(null); // null | 'up' | 'down'

  async function handleFeedback(helpful) {
    const type = helpful ? 'up' : 'down';
    setFeedback(type);
    try { await sendFeedback(question, contexts, helpful); } catch {}
  }

  function handleCopy(btn) {
    const contentEl = btn.closest('.message')?.querySelector('.message-content');
    if (contentEl) {
      navigator.clipboard.writeText(contentEl.textContent);
      btn.textContent = '已复制';
      setTimeout(() => { btn.textContent = '复制'; }, 1500);
    }
  }

  const done = feedback !== null;

  return (
    <div className="msg-actions">
      <button onClick={(e) => handleCopy(e.target)}>复制</button>
      <button onClick={onRegenerate}>重新生成</button>
      <button
        onClick={() => !done && handleFeedback(true)}
        style={{ color: feedback === 'up' ? 'var(--gold)' : undefined, fontWeight: feedback === 'up' ? 700 : undefined }}
      >
        {feedback === 'up' ? '已赞' : '赞'}
      </button>
      <button
        onClick={() => !done && handleFeedback(false)}
        style={{ color: feedback === 'down' ? 'var(--vermilion)' : undefined }}
      >
        {feedback === 'down' ? '已踩' : '踩'}
      </button>
      <button onClick={onDelete} style={{ marginLeft: 6 }}>删除</button>
    </div>
  );
}
