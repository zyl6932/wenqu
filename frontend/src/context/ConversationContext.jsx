import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'wenqu_conversations';
const ACTIVE_KEY = 'wenqu_active_conv';
const HISTORY_KEY = 'wenqu_search_history';

function loadConversations() {
  try {
    const convs = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    // 清理僵尸消息：刷新中断导致 AI 消息无内容无耗时
    for (const c of convs) {
      if (!c.messages?.length) continue;
      const last = c.messages[c.messages.length - 1];
      if (last && last.role === 'ai' && !last.content && !last.elapsed) {
        last.content = '[生成被中断，请重新发送问题]';
        last.thinkingContent = '';
      }
    }
    return convs;
  } catch { return []; }
}
function saveConversations(convs) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(convs)); } catch {}
}
function loadActive(convs) {
  const id = localStorage.getItem(ACTIVE_KEY);
  return (id && convs.find(c => c.id === id)) ? id : (convs.length > 0 ? convs[0].id : null);
}

function convReducer(state, action) {
  let next;
  switch (action.type) {
    case 'LOAD':
      return { ...state, conversations: action.convs, activeConvId: loadActive(action.convs), filter: '' };
    case 'NEW': {
      const conv = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: '新对话', createdAt: Date.now(), messages: [] };
      next = { ...state, conversations: [conv, ...state.conversations], activeConvId: conv.id };
      break;
    }
    case 'SWITCH':
      next = { ...state, activeConvId: action.id };
      break;
    case 'RENAME': {
      next = { ...state, conversations: state.conversations.map(c => c.id === action.id ? { ...c, title: action.title } : c) };
      break;
    }
    case 'DELETE': {
      const filtered = state.conversations.filter(c => c.id !== action.id);
      next = { ...state, conversations: filtered, activeConvId: state.activeConvId === action.id ? (filtered[0]?.id || null) : state.activeConvId };
      break;
    }
    case 'ADD_USER_MSG': {
      // 自动创建对话（首次发送时）
      if (!state.activeConvId || !state.conversations.find(c => c.id === state.activeConvId)) {
        const newConv = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: '新对话', createdAt: Date.now(), messages: [] };
        state = { ...state, conversations: [newConv, ...state.conversations], activeConvId: newConv.id };
      }
      const conv = state.conversations.find(c => c.id === state.activeConvId);
      if (!conv) return state;
      const title = conv.title;
      next = {
        ...state,
        conversations: state.conversations.map(c => c.id === state.activeConvId
          ? { ...c, title, messages: [...c.messages, { role: 'user', content: action.content, timestamp: Date.now() }] }
          : c)
      };
      break;
    }
    case 'ADD_AI_MSG': {
      next = {
        ...state,
        conversations: state.conversations.map(c => c.id === state.activeConvId
          ? { ...c, messages: [...c.messages, { role: 'ai', content: '', thinkingContent: '', sources: [], timestamp: Date.now() }] }
          : c)
      };
      break;
    }
    case 'APPEND_THINK': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = [...c.messages];
          if (msgs.length && msgs[msgs.length - 1].role === 'ai') {
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], thinkingContent: msgs[msgs.length - 1].thinkingContent + action.token };
          }
          return { ...c, messages: msgs };
        })
      };
      break;
    }
    case 'APPEND_TOKEN': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = [...c.messages];
          if (msgs.length && msgs[msgs.length - 1].role === 'ai') {
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: msgs[msgs.length - 1].content + action.token };
          }
          return { ...c, messages: msgs };
        })
      };
      break;
    }
    case 'SET_SOURCES': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = [...c.messages];
          if (msgs.length && msgs[msgs.length - 1].role === 'ai') {
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], sources: action.sources };
          }
          return { ...c, messages: msgs };
        })
      };
      break;
    }
    case 'FINISH_AI_MSG': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = [...c.messages];
          if (msgs.length && msgs[msgs.length - 1].role === 'ai') {
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], timestamp: Date.now(), elapsed: action.elapsed };
          }
          return { ...c, messages: msgs };
        })
      };
      break;
    }
    case 'DELETE_MESSAGE': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = c.messages.filter((_, i) => i !== action.idx);
          return { ...c, messages: msgs, title: msgs.length === 0 ? '新对话' : c.title };
        })
      };
      break;
    }
    case 'POP_LAST_AI': {
      next = {
        ...state,
        conversations: state.conversations.map(c => {
          if (c.id !== state.activeConvId) return c;
          const msgs = [...c.messages];
          if (msgs.length && msgs[msgs.length - 1].role === 'ai') msgs.pop();
          return { ...c, messages: msgs };
        })
      };
      break;
    }
    case 'SET_FILTER':
      next = { ...state, filter: action.filter };
      break;
    default:
      return state;
  }
  saveConversations(next.conversations);
  if (next.activeConvId !== state.activeConvId) {
    try { localStorage.setItem(ACTIVE_KEY, next.activeConvId || ''); } catch {}
  }
  return next;
}

const ConversationContext = createContext(null);

export function ConversationProvider({ children }) {
  const [state, dispatch] = useReducer(convReducer, {
    conversations: [],
    activeConvId: null,
    filter: '',
  });

  useEffect(() => {
    const convs = loadConversations();
    dispatch({ type: 'LOAD', convs });
  }, []);

  // search history helpers
  const addSearchHistory = useCallback((q) => {
    if (!q || q.length < 2) return;
    try {
      let h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
      h = h.filter(item => item !== q);
      h.unshift(q);
      if (h.length > 20) h = h.slice(0, 20);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
    } catch {}
  }, []);

  const getSearchHistory = useCallback(() => {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; }
  }, []);

  const cleanOrphanHistory = useCallback(() => {
    const allQuestions = new Set();
    state.conversations.forEach(c => c.messages.filter(m => m.role === 'user').forEach(m => allQuestions.add(m.content.trim())));
    try {
      let h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]').filter(q => allQuestions.has(q.trim()));
      localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
    } catch {}
  }, [state.conversations]);

  const getActiveConv = useCallback(() => {
    return state.conversations.find(c => c.id === state.activeConvId) || null;
  }, [state.conversations, state.activeConvId]);

  return (
    <ConversationContext.Provider value={{
      state, dispatch,
      addSearchHistory, getSearchHistory, cleanOrphanHistory,
      getActiveConv,
    }}>
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  return useContext(ConversationContext);
}
