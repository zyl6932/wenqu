import React, { useRef, useState, useCallback, useEffect } from 'react';
import { useConversation } from '../../context/ConversationContext';
import { useToast } from '../../context/ToastContext';
import { askStream, genTitle } from '../../api/client';
import MessageList from './MessageList';
import ChatInput from './ChatInput';

export default function ChatArea({ sidebarCollapsed }) {
  const { state, dispatch, addSearchHistory, getActiveConv } = useConversation();
  const { addToast } = useToast();
  const [isStreaming, setIsStreaming] = useState(false);
  const [elapsed, setElapsed] = useState(null);
  const [fillValue, setFillValue] = useState({ text: null, key: 0 });
  const [atBottom, setAtBottom] = useState(true);
  const thinkCountRef = useRef(0);
  const outCountRef = useRef(0);
  const stopRef = useRef(null);
  const msgListRef = useRef(null);

  const handleSend = useCallback((question) => {
    const prevMessages = getActiveConv()?.messages || [];
    addSearchHistory(question);

    thinkCountRef.current = 0;
    outCountRef.current = 0;

    const convBefore = getActiveConv();

    dispatch({ type: 'ADD_USER_MSG', content: question });
    dispatch({ type: 'ADD_AI_MSG' });

    // 新对话 → 异步生成标题
    if ((!convBefore || convBefore.title === '新对话') && prevMessages.length === 0) {
      genTitle(question).then(data => {
        const newConv = getActiveConv();
        if (newConv && data?.title) {
          dispatch({ type: 'RENAME', id: newConv.id, title: data.title });
        }
      }).catch(() => {});
    }

    const history = prevMessages
      .filter(m => m.role !== 'ai' || m.content)
      .map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.content }));

    setIsStreaming(true);
    setElapsed(null);

    const stop = askStream(
      question,
      history.length > 1 ? history.slice(0, -1) : null,
      null,
      (token) => { outCountRef.current++; dispatch({ type: 'APPEND_TOKEN', token }); },
      (think) => { thinkCountRef.current++; dispatch({ type: 'APPEND_THINK', token: think }); },
      (sources) => dispatch({ type: 'SET_SOURCES', sources }),
      (thinking) => {
        thinkCountRef.current += Math.round(thinking.length * 0.6);
        dispatch({ type: 'APPEND_THINK', token: thinking + '\n' });
      },
      (elapsedStr, aborted) => {
        setIsStreaming(false);
        stopRef.current = null;
        if (!aborted) {
          setElapsed(elapsedStr);
          dispatch({ type: 'FINISH_AI_MSG', elapsed: elapsedStr,
            thinkTokens: thinkCountRef.current,
            outTokens: outCountRef.current });
        } else {
          dispatch({ type: 'FINISH_AI_MSG', elapsed: null, thinkTokens: null, outTokens: null });
        }
      },
      (err) => {
        setIsStreaming(false);
        stopRef.current = null;
        dispatch({ type: 'APPEND_TOKEN', token: `\n[${err}]` });
        dispatch({ type: 'FINISH_AI_MSG', elapsed: null });
        addToast(err, 'error');
      },
      localStorage.getItem('wenqu_use_local') === 'true' ? 'ollama' : null
    );
    stopRef.current = stop;
  }, [state.conversations, dispatch, addSearchHistory, getActiveConv, addToast]);

  const handleStop = useCallback(() => {
    if (stopRef.current) stopRef.current();
    setIsStreaming(false);
  }, []);

  useEffect(() => {
    const handler = () => { if (stopRef.current) stopRef.current(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);

  const conv = getActiveConv();

  return (
    <div className="main">
      <div className="chat-header" style={{ paddingLeft: sidebarCollapsed ? 52 : 16 }}>
        <span className="chat-header-title">{conv?.title || '问渠'}</span>
      </div>
      <MessageList
        ref={msgListRef}
        elapsed={elapsed}
        isStreaming={isStreaming}
        onFillInput={(q) => setFillValue({ text: q, key: Date.now() })}
        onScrollStateChange={setAtBottom}
      />
      {!atBottom && (
        <div style={{ position: 'relative', zIndex: 6, display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={() => {
              const el = document.querySelector('.chat-messages');
              if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
            }}
            style={{
              position: 'absolute', bottom: 8,
              width: 32, height: 32, borderRadius: '50%',
              border: '1px solid var(--border)', background: 'var(--surface)',
              color: 'var(--ink-soft)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: 'var(--shadow)',
            }}
            title="回到底部"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
      )}
      <ChatInput
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        fillValue={fillValue}
      />
    </div>
  );
}
