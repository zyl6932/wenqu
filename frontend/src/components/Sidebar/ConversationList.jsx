import React from 'react';
import { useConversation } from '../../context/ConversationContext';
import { groupByTime } from '../../utils/grouping';
import ConversationItem from './ConversationItem';

export default function ConversationList() {
  const { state, dispatch } = useConversation();
  const filtered = state.filter
    ? state.conversations.filter(c => c.title.toLowerCase().includes(state.filter.toLowerCase()))
    : state.conversations;

  if (!filtered.length) {
    return (
      <div className="conv-section">
        <div className="conv-section-header">对话历史</div>
        <div className="conv-empty">暂无对话</div>
      </div>
    );
  }

  const { groups, labels } = groupByTime(filtered);

  return (
    <div className="conv-section">
      <div className="conv-section-header">对话历史 <span style={{ float: 'right', fontWeight: 400 }}>{state.conversations.length || ''}</span></div>
      {Object.entries(labels).map(([key, label]) => {
        const items = groups[key];
        if (!items.length) return null;
        return (
          <React.Fragment key={key}>
            <div className="conv-section-header" style={{ padding: '6px 4px 2px' }}>{label} <span style={{ float: 'right', fontWeight: 400 }}>{items.length}</span></div>
            {items.map(c => (
              <ConversationItem
                key={c.id}
                conv={c}
                isActive={c.id === state.activeConvId}
                onSelect={id => dispatch({ type: 'SWITCH', id })}
                onRename={id => {
                  const title = prompt('重命名对话', c.title);
                  if (title?.trim()) dispatch({ type: 'RENAME', id, title: title.trim() });
                }}
                onDelete={id => {
                  if (confirm('确定删除此对话？')) dispatch({ type: 'DELETE', id });
                }}
              />
            ))}
          </React.Fragment>
        );
      })}
    </div>
  );
}
