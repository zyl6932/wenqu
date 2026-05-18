import React, { useEffect, useRef, useState } from 'react';
import { renderMarkdown } from '../../utils/markdown';

export default function MessageContent({ role, content, thinkingContent, isStreaming, elapsed }) {
  const ref = useRef(null);
  const [thinkOpen, setThinkOpen] = useState(false);

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

  const html = renderMarkdown(content);
  const showCursor = isStreaming && content;
  const cls = showCursor ? 'mc-ai message-content streaming-cursor' : 'mc-ai message-content';

  if (!thinkingContent) {
    return <div ref={ref} className={cls} dangerouslySetInnerHTML={{ __html: html }} />;
  }

  const headerText = elapsed ? `已思考 · ${elapsed}s` : '思考中…';

  return (
    <div ref={ref} className={cls}>
      <div style={{ fontSize: 12, color: 'var(--ink-mute)', marginBottom: 4, cursor: 'pointer' }} onClick={() => setThinkOpen(v => !v)}>
        {headerText} {thinkOpen ? '▾' : '▸'}
      </div>
      {thinkOpen && <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--ink-mute)', lineHeight: 1.6, marginBottom: 8 }}>{thinkingContent.replace(/^\s+/, '')}</div>}
      {content && <div dangerouslySetInnerHTML={{ __html: html }} />}
    </div>
  );
}
