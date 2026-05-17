import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useAutoResize } from '../../hooks/useAutoResize';
import { useConversation } from '../../context/ConversationContext';
import SearchHistoryDropdown from './SearchHistoryDropdown';

export default function ChatInput({ onSend, onStop, isStreaming, inputRef }) {
  const [value, setValue] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const textareaRef = useRef(null);
  const autoResize = useAutoResize();
  const { getSearchHistory } = useConversation();

  useEffect(() => {
    if (inputRef) inputRef.current = textareaRef.current;
  }, [inputRef]);

  const history = getSearchHistory();

  function handleInput(e) {
    setValue(e.target.value);
    autoResize(e.target);
  }

  function handleKeyDown(e) {
    if (isComposing || e.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSend() {
    const q = value.trim();
    if (!q || isStreaming) return;
    setValue('');
    setShowHistory(false);
    const el = textareaRef.current;
    if (el) { el.style.height = 'auto'; el.style.overflowY = 'hidden'; }
    onSend(q);
  }

  function handlePaste(e) {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData('text/plain');
    document.execCommand('insertText', false, text);
  }

  function handleFocus() {
    setIsComposing(false);
    if (!value) setShowHistory(true);
  }

  return (
    <div className="chat-input-area" style={{ position: 'relative' }}>
      {showHistory && <SearchHistoryDropdown items={history} onSelect={(q) => { if (q) { setValue(q); setShowHistory(false); } else setShowHistory(false); }} />}
      <div className="input-wrapper">
        <textarea
          ref={textareaRef}
          rows="1"
          placeholder="输入问题... (Enter 发送, Ctrl+K 聚焦)"
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          onFocus={handleFocus}
          onPaste={handlePaste}
        />
        <button className="btn-send" disabled={!value.trim() && !isStreaming} onClick={isStreaming ? onStop : handleSend}>
          {isStreaming ? (
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
          )}
        </button>
      </div>
    </div>
  );
}
