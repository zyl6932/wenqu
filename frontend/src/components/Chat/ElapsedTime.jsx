import React from 'react';

export default function ElapsedTime({ seconds, thinkTokens, outTokens }) {
  if (!seconds) return null;
  const parts = [];
  if (thinkTokens) parts.push(`${thinkTokens} token 思考`);
  if (outTokens) parts.push(`${outTokens} token 输出`);
  const info = parts.length ? parts.join(' · ') + ' · ' : '';
  return (
    <div style={{ fontSize: 11, color: 'var(--ink-mute)', marginTop: 4, fontFamily: 'var(--serif)' }}>
      {info}耗时 {seconds}s
    </div>
  );
}
