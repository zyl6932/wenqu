import React, { useState, useRef, useEffect } from 'react';
import { useAutoResize } from '../../hooks/useAutoResize';
import { useConversation } from '../../context/ConversationContext';
import SearchHistoryDropdown from './SearchHistoryDropdown';

export default function ChatInput({ onSend, onStop, isStreaming, fillValue, inputRef }) {
  const [value, setValue] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [hoverIndex, setHoverIndex] = useState(-1);
  const [longPressActive, setLongPressActive] = useState(false);
  const textareaRef = useRef(null);
  const longPressTimer = useRef(null);
  const autoResize = useAutoResize();
  const { getSearchHistory } = useConversation();

  useEffect(() => {
    if (inputRef) inputRef.current = textareaRef.current;
  }, [inputRef]);

  useEffect(() => {
    if (fillValue?.text) {
      setValue(fillValue.text);
      setShowHistory(false);
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          autoResize(textareaRef.current);
        }
      }, 0);
    }
  }, [fillValue?.key]);

  useEffect(() => {
    return () => { if (longPressTimer.current) clearTimeout(longPressTimer.current); };
  }, []);

  const history = getSearchHistory();

  function handleInput(e) {
    setValue(e.target.value);
    autoResize(e.target);
  }

  function handleKeyDown(e) {
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter' && !e.shiftKey && window.innerWidth > 768) {
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
    if (!longPressActive) setShowHistory(false);
  }

  // 长按 500ms 弹出历史
  function handlePointerDown(e) {
    if (e.button !== 0) return;
    longPressTimer.current = setTimeout(() => {
      setLongPressActive(true);
      setShowHistory(true);
      setHoverIndex(-1);
    }, 500);
  }

  function handlePointerUp(e) {
    clearTimeout(longPressTimer.current);
    if (longPressActive) {
      // 长按模式下松开：选择当前高亮项
      const items = history?.slice(0, 8);
      if (hoverIndex >= 0 && items?.[hoverIndex]) {
        setValue(items[hoverIndex]);
        setShowHistory(false);
      } else {
        setShowHistory(false);
      }
      setLongPressActive(false);
      e.preventDefault();
    }
  }

  function handlePointerMove(e) {
    if (!longPressActive || !showHistory) return;
    // 根据鼠标位置计算高亮项
    const dropdown = document.querySelector('.history-dropdown');
    if (!dropdown) return;
    const items = dropdown.querySelectorAll('[data-hist-item]');
    const rect = dropdown.getBoundingClientRect();
    if (e.clientY < rect.top || e.clientY > rect.bottom) {
      setHoverIndex(-1);
      return;
    }
    const y = e.clientY - rect.top;
    const idx = Math.floor(y / 36); // 每项约 36px
    setHoverIndex(Math.min(Math.max(idx, 0), (items.length || 1) - 1));
  }

  function handlePointerCancel() {
    clearTimeout(longPressTimer.current);
    setLongPressActive(false);
    setShowHistory(false);
  }

  return (
    <div className="chat-input-area">
      <div className="input-wrapper" style={{ position: 'relative' }}>
      {showHistory && (
        <SearchHistoryDropdown
          items={history}
          hoverIndex={hoverIndex}
          onHoverIndex={setHoverIndex}
          longPressMode={longPressActive}
          onSelect={(q) => { if (q) { setValue(q); setShowHistory(false); } else setShowHistory(false); }}
        />
      )}
        <textarea
          ref={textareaRef}
          rows="1"
          placeholder={window.innerWidth > 768 ? "输入问题... (Enter 发送, Ctrl+K 聚焦)" : "输入问题..."}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onCompositionEnd={() => {}}
          onFocus={handleFocus}
          onPaste={handlePaste}
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerMove={handlePointerMove}
          onPointerCancel={handlePointerCancel}
          onPointerLeave={handlePointerCancel}
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
