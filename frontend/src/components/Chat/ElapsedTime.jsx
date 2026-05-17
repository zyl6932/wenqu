import React from 'react';

export default function ElapsedTime({ seconds }) {
  if (!seconds) return null;
  return (
    <div style={{ fontSize: 11, color: 'var(--ink-mute)', marginTop: 4, fontFamily: 'var(--serif)' }}>
      耗时 {seconds}s
    </div>
  );
}
