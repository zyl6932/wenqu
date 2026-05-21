import React from 'react';
import MessageContent from './MessageContent';
import MessageSources from './MessageSources';
import MessageActions from './MessageActions';
import ElapsedTime from './ElapsedTime';

export default function MessageItem({ msg, prevQuestion, isLastAI, isStreaming, elapsed, onRegenerate, onDelete }) {
  const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '';

  if (msg.role === 'user') {
    return (
      <div className="message user">
        <MessageContent role="user" content={msg.content} />
        {ts && <div className="msg-time user">{ts}</div>}
        <div className="msg-actions" style={{ justifyContent: 'flex-end', marginTop: 2 }}>
          <button onClick={onDelete} style={{ fontSize: 11, color: 'var(--ink-mute)', border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--serif)' }}>删除</button>
        </div>
      </div>
    );
  }

  const hasContent = !!msg.content;
  return (
    <div className="message ai">
      <MessageContent role="ai" content={msg.content} thinkingContent={msg.thinkingContent} isStreaming={isStreaming} elapsed={isLastAI ? elapsed : null} msgElapsed={msg.elapsed} />
      {ts && !(isLastAI && isStreaming) && <div className="msg-time" style={{ paddingLeft: 2 }}>{ts}</div>}
      {hasContent && <MessageSources sources={msg.sources} />}
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
