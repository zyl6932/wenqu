import React from 'react';
import MessageContent from './MessageContent';
import MessageSources from './MessageSources';
import MessageActions from './MessageActions';
import ElapsedTime from './ElapsedTime';

export default function MessageItem({ msg, prevQuestion, isLastAI, isStreaming, elapsed, onRegenerate, onDelete }) {
  const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '';

  if (msg.role === 'user') {
    function copyUserMsg(btn) {
      const contentEl = btn.closest('.message')?.querySelector('.message-content');
      if (contentEl) {
        navigator.clipboard.writeText(contentEl.textContent);
        btn.textContent = '已复制';
        setTimeout(() => { btn.textContent = '复制'; }, 1500);
      }
    }
    return (
      <div className="message user">
        <MessageContent role="user" content={msg.content} />
        {ts && <div className="msg-time user">{ts}</div>}
        <div className="msg-actions" style={{ justifyContent: 'flex-end', marginTop: 2 }}>
          <button onClick={(e) => copyUserMsg(e.target)} style={{ color: 'var(--ink-mute)', border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--serif)' }}>复制</button>
          <button onClick={onDelete} style={{ color: 'var(--ink-mute)', border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--serif)' }}>删除</button>
        </div>
      </div>
    );
  }

  const hasContent = !!msg.content;
  return (
    <div className="message ai">
      <MessageContent role="ai" content={msg.content} thinkingContent={msg.thinkingContent} isStreaming={isStreaming} elapsed={isLastAI ? elapsed : null} msgElapsed={msg.elapsed} />
      {ts && !(isLastAI && isStreaming) && <div className="msg-time">{ts}</div>}
      {hasContent && msg.elapsed && <MessageSources sources={msg.sources} />}
      {(msg.elapsed || (isLastAI && elapsed)) && <ElapsedTime seconds={elapsed || msg.elapsed} thinkTokens={msg.thinkTokens} outTokens={msg.outTokens} />}
      {hasContent && (
        <MessageActions
          question={prevQuestion}
          contexts={[msg.content]}
          onRegenerate={() => onRegenerate(prevQuestion)}
          onDelete={onDelete}
        />
      )}
    </div>
  );
}
