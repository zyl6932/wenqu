import React, { useEffect, useRef } from 'react';
import { renderMarkdown } from '../../utils/markdown';

export default function MessageContent({ role, content }) {
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

  const html = renderMarkdown(content);
  return (
    <div ref={ref} className="mc-ai message-content" dangerouslySetInnerHTML={{ __html: html }} />
  );
}
