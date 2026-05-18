import React, { useEffect, useRef, useState } from 'react';
import { renderMarkdown } from '../../utils/markdown';

export default function MessageContent({ role, content, thinkingContent, isStreaming, elapsed }) {
  const ref = useRef(null);
  const [thinkOpen, setThinkOpen] = useState(true);

  useEffect(() => {
    if (role !== 'ai' || !ref.current) return;
    const pres = ref.current.querySelectorAll('pre');
    pres.forEach(pre => {
      if (pre.querySelector('.code-copy-btn')) return;
      const btn = document.createElement('button');
      btn.className = 'code-copy-btn';
      btn.textContent = '复制';
      btn.onclick = async () => {
        const code = pre.querySelector('code');
        if (code) {
          try { await navigator.clipboard.writeText(code.textContent); } catch {}
          btn.textContent = '已复制';
          setTimeout(() => { btn.textContent = '复制'; }, 1500);
        }
      };
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
  }, [role, content, thinkingContent]);

  if (role === 'user') {
    return <div className="mc-user message-content">{content}</div>;
  }

  if (!content && !thinkingContent) {
    return <div className="mc-ai message-content"><span className="thinking-text">思考中</span></div>;
  }

  const cls = isStreaming ? 'mc-ai message-content streaming-cursor' : 'mc-ai message-content';
  const html = renderMarkdown(content);

  if (!thinkingContent) {
    return <div ref={ref} className={cls} dangerouslySetInnerHTML={{ __html: html }} />;
  }

  const headerText = elapsed ? `已思考 · ${elapsed}s` : '思考中…';

  return (
    <div ref={ref} className={cls}>
      <div className="think-card" onClick={() => setThinkOpen(v => !v)}>
        <div className="think-card-header">
          <span className={`think-arrow${thinkOpen ? ' open' : ''}`}>▸</span>
          <span className="think-card-title">{headerText}</span>
        </div>
        <div className={`think-card-body${thinkOpen ? ' open' : ''}`}>
          <div className="think-card-text">{thinkingContent}</div>
        </div>
      </div>
      {content && <div className="think-answer" dangerouslySetInnerHTML={{ __html: html }} />}
    </div>
  );
}
