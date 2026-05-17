import React from 'react';

const QUICK_STARTS = [
  'Ollama怎么安装',
  '机器视觉特征提取',
  '实习安全教育',
];

export default function EmptyChat({ onFillInput }) {
  return (
    <div className="empty-chat">
      <div className="empty-chat-icon">知</div>
      <h3>知识库助手</h3>
      <p>向 AI 提问，我会基于已导入的文档为你查找答案。</p>
      <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
        {QUICK_STARTS.map(q => (
          <button key={q} className="quick-btn" onClick={() => onFillInput(q)}>{q}</button>
        ))}
      </div>
    </div>
  );
}
