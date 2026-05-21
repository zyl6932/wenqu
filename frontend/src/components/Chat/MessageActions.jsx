import React, { useState } from 'react';
import { sendFeedback } from '../../api/client';

export default function MessageActions({ question, contexts, onRegenerate, onDelete }) {
  const [feedback, setFeedback] = useState(0); // 0=none, 1=赞, -1=踩

  function handleFeedback(helpful) {
    const newVal = feedback === helpful ? 0 : helpful;
    setFeedback(newVal);
    try { sendFeedback(question, contexts, newVal > 0); } catch {}
  }

  function handleCopy(btn) {
    const contentEl = btn.closest('.message')?.querySelector('.message-content');
    if (contentEl) {
      navigator.clipboard.writeText(contentEl.textContent);
      btn.textContent = '已复制';
      setTimeout(() => { btn.textContent = '复制'; }, 1500);
    }
  }

  return (
    <div className="msg-actions">
      <button onClick={(e) => handleCopy(e.target)}>复制</button>
      <button onClick={onRegenerate}>重新生成</button>
      <button
        onClick={() => handleFeedback(1)}
        style={{ color: feedback === 1 ? 'var(--gold)' : undefined, fontWeight: feedback === 1 ? 700 : undefined }}
      >
        {feedback === 1 ? '已赞' : '赞'}
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        style={{ color: feedback === -1 ? 'var(--vermilion)' : undefined }}
      >
        {feedback === -1 ? '已踩' : '踩'}
      </button>
      <button onClick={onDelete} style={{ marginLeft: 6 }}>删除</button>
    </div>
  );
}
