import React from 'react';
import { useConversation } from '../../context/ConversationContext';
import { useToast } from '../../context/ToastContext';
import { escAttr } from '../../utils/grouping';

export default function ExportButton() {
  const { getActiveConv } = useConversation();
  const { addToast } = useToast();

  function handleExport() {
    const conv = getActiveConv();
    if (!conv || !conv.messages.length) { addToast('对话为空', 'error'); return; }
    let md = `# ${conv.title}\n\n`;
    for (const m of conv.messages) {
      if (m.role === 'user') md += `> ${m.content}\n\n`;
      else { md += `${m.content}\n\n`; if (m.sources?.length) md += `*来源: ${m.sources.map(s => typeof s === 'string' ? s : s.name).join(', ')}*\n\n`; }
    }
    md += `\n---\n*${new Date().toLocaleString()}*\n`;
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${conv.title.replace(/[^a-zA-Z0-9一-龥]/g, '_')}.md`;
    a.click();
  }

  return (
    <button className="sidebar-btn" onClick={handleExport} style={{ width: '100%', fontSize: 12 }}>导出当前对话</button>
  );
}
