import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useConversation } from '../../context/ConversationContext';
import MessageItem from './MessageItem';
import EmptyChat from './EmptyChat';
import ScrollToBottomBtn from './ScrollToBottomBtn';

export default function MessageList({ elapsed, isStreaming, onFillInput }) {
  const { getActiveConv, dispatch } = useConversation();
  const conv = getActiveConv();
  const containerRef = useRef(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const lastContent = conv?.messages.length ? conv.messages[conv.messages.length - 1].content : '';

  const scrollToBottom = useCallback(() => {
    if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, []);

  // 新消息时滚动 + 流式输出时跟随滚动
  useEffect(() => { scrollToBottom(); }, [conv?.messages.length, lastContent, scrollToBottom]);

  // 流式结束后补一次滚动（耗时/操作按钮出现可能改变高度）
  useEffect(() => {
    if (!isStreaming && elapsed) scrollToBottom();
  }, [isStreaming, elapsed, scrollToBottom]);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 2000);
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
      <ScrollToBottomBtn visible={showScrollBtn} onClick={scrollToBottom} />
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
            key={idx}
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
