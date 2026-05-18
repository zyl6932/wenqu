import React, { useEffect, useRef } from 'react';
import { renderMarkdown } from '../../utils/markdown';

export default function MessageContent({ role, content, isStreaming }) {
  const ref = useRef(null);

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
  }, [role, content]);

  if (role === 'user') {
    return <div className="mc-user message-content">{content}</div>;
  }

  if (!content) {
    return <div className="mc-ai message-content"><span className="thinking-text">思考中</span></div>;
  }

  const cls = isStreaming ? 'mc-ai message-content streaming-cursor' : 'mc-ai message-content';
  const html = renderMarkdown(content);
  return (
    <div ref={ref} className={cls} dangerouslySetInnerHTML={{ __html: html }} />
  );
}
