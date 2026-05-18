import React, { useRef, useState, useCallback } from 'react';
import { useConversation } from '../../context/ConversationContext';
import { useToast } from '../../context/ToastContext';
import { askStream } from '../../api/client';
import MessageList from './MessageList';
import ChatInput from './ChatInput';

export default function ChatArea() {
  const { state, dispatch, addSearchHistory, getActiveConv } = useConversation();
  const { addToast } = useToast();
  const [isStreaming, setIsStreaming] = useState(false);
  const [elapsed, setElapsed] = useState(null);
  const stopRef = useRef(null);
  const inputRef = useRef(null);

  const handleSend = useCallback((question) => {
    // 在 dispatch 前捕获历史，避免闭包读取到过期状态
    const prevMessages = getActiveConv()?.messages || [];
    addSearchHistory(question);

    dispatch({ type: 'ADD_USER_MSG', content: question });
    dispatch({ type: 'ADD_AI_MSG' });

    const history = prevMessages
      .filter(m => m.role !== 'ai' || m.content)
      .map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.content }));

    setIsStreaming(true);
    setElapsed(null);

    const stop = askStream(
      question,
      history.length > 1 ? history.slice(0, -1) : null,
      null,
      (token) => dispatch({ type: 'APPEND_TOKEN', token }),
      (sources) => dispatch({ type: 'SET_SOURCES', sources }),
      (elapsedStr, aborted) => {
        setIsStreaming(false);
        stopRef.current = null;
        dispatch({ type: 'FINISH_AI_MSG' });
        if (!aborted) setElapsed(elapsedStr);
      },
      (err) => {
        setIsStreaming(false);
        stopRef.current = null;
        dispatch({ type: 'APPEND_TOKEN', token: `\n[${err}]` });
        dispatch({ type: 'FINISH_AI_MSG' });
        addToast(err, 'error');
      }
    );
    stopRef.current = stop;
  }, [state.conversations, dispatch, addSearchHistory, getActiveConv, addToast]);

  const handleStop = useCallback(() => {
    if (stopRef.current) stopRef.current();
    setIsStreaming(false);
  }, []);

  const handleFillInput = useCallback((q) => {
    if (inputRef.current) {
      inputRef.current.value = q;
      inputRef.current.focus();
    }
  }, []);

  return (
    <div className="main">
      <MessageList elapsed={elapsed} isStreaming={isStreaming} onFillInput={handleFillInput} />
      <ChatInput
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        inputRef={inputRef}
      />
    </div>
  );
}
