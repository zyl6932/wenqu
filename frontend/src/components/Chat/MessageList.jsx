import React, { useRef, useEffect, useCallback } from 'react';
import { useConversation } from '../../context/ConversationContext';
import MessageItem from './MessageItem';
import EmptyChat from './EmptyChat';

export default function MessageList({ elapsed, isStreaming, onFillInput, onScrollStateChange }) {
  const { getActiveConv, dispatch } = useConversation();
  const conv = getActiveConv();
  const containerRef = useRef(null);

  const lastContent = conv?.messages.length ? conv.messages[conv.messages.length - 1].content : '';

  const scrollToBottom = useCallback(() => {
    if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, []);

  const checkAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, []);

  // 新消息时滚动 + 流式输出时跟随滚动
  useEffect(() => { scrollToBottom(); }, [conv?.messages.length, lastContent, scrollToBottom]);

  // 流式结束后补一次滚动
  useEffect(() => {
    if (!isStreaming && elapsed) scrollToBottom();
  }, [isStreaming, elapsed, scrollToBottom]);

  function handleScroll() {
    onScrollStateChange?.(checkAtBottom());
  }

  if (!conv || !conv.messages.length) {
    return (
      <div className="chat-messages" ref={containerRef}>
        <EmptyChat onFillInput={onFillInput} />
      </div>
    );
  }

  return (
    <div className="chat-messages" ref={containerRef} onScroll={handleScroll}>
      {conv.messages.map((m, idx) => {
        let prevQ = '';
        if (m.role === 'ai') {
          for (let j = idx - 1; j >= 0; j--) {
            if (conv.messages[j].role === 'user') { prevQ = conv.messages[j].content; break; }
          }
        }
        const lastAI = m.role === 'ai' && idx === conv.messages.length - 1;
        return (
          <MessageItem
            key={m._id || idx}
            msg={m}
            prevQuestion={prevQ}
            isLastAI={lastAI}
            isStreaming={lastAI && isStreaming}
            elapsed={lastAI ? elapsed : null}
            onRegenerate={(q) => { if (q) { dispatch({ type: 'POP_LAST_AI' }); onFillInput(q); } }}
            onDelete={() => { if (confirm(`确定删除此消息？\n"${m.content.slice(0, 30)}${m.content.length > 30 ? '...' : ''}"`)) dispatch({ type: 'DELETE_MESSAGE', idx }); }}
          />
        );
      })}
    </div>
  );
}
