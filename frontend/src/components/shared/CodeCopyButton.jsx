import React, { useState } from 'react';

export default function CodeCopyButton({ code }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="code-copy-btn"
      onClick={async () => {
        try { await navigator.clipboard.writeText(code); } catch {}
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      style={copied ? { color: '#a6e3a1' } : undefined}
    >
      {copied ? '已复制' : '复制'}
    </button>
  );
}
