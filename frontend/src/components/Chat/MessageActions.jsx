import React, { useState } from 'react';
import { sendFeedback } from '../../api/client';

export default function MessageActions({ question, contexts, onRegenerate, onDelete }) {
  const [feedbackDone, setFeedbackDone] = useState(false);

  async function handleFeedback(helpful) {
    try {
      await sendFeedback(question, contexts, helpful);
    } catch {}
    setFeedbackDone(true);
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
      <button onClick={() => !feedbackDone && handleFeedback(true)} className={feedbackDone ? 'done' : ''}>赞</button>
      <button onClick={() => !feedbackDone && handleFeedback(false)} className={feedbackDone ? 'done' : ''}>踩</button>
      <button onClick={onDelete} style={{ marginLeft: 6 }}>删除</button>
    </div>
  );
}
