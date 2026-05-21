import React, { useState, useEffect } from 'react';
import ThemeToggle from './ThemeToggle';
import FontSizeControl from './FontSizeControl';
import ExportButton from './ExportButton';
import DocSection from './DocSection';
import { fetchConfig, updateConfig } from '../../api/client';
import { useToast } from '../../context/ToastContext';

export default function SettingsPanel({ visible, onOpenChunks }) {
  const [cfg, setCfg] = useState(null);
  const [dirty, setDirty] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (!visible) return;
    fetchConfig().then(setCfg).catch(() => {});
  }, [visible]);

  function setVal(key, val) {
    setCfg(prev => ({ ...prev, [key]: val }));
    setDirty(true);
  }

  async function handleSave() {
    try {
      const res = await updateConfig(cfg);
      addToast(res.message || '已更新');
      setDirty(false);
    } catch { addToast('更新失败', 'error'); }
  }

  if (!visible) return null;

  return (
    <div style={{ borderTop: '1px solid var(--border)' }}>
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--bg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>主题</span>
          <ThemeToggle />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>LLM 模型</span>
          <button
            className="sidebar-btn"
            onClick={() => {
              const cur = localStorage.getItem('wenqu_use_local') === 'true';
              localStorage.setItem('wenqu_use_local', !cur);
              // 强制刷新 sidebar 更新按钮文字
              window.dispatchEvent(new Event('storage'));
              setCfg(cfg => cfg ? { ...cfg } : cfg);
            }}
            style={{ width: 'auto', padding: '4px 10px', fontSize: 12 }}
          >
            {localStorage.getItem('wenqu_use_local') === 'true' ? '本地' : '联网'}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>字号</span>
          <FontSizeControl />
        </div>

        {cfg && (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--ink-mute)', fontFamily: 'var(--serif)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.1em' }}>检索设置</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>相似度阈值</span>
                <span style={{ fontSize: 11, color: 'var(--vermilion)', minWidth: 24, textAlign: 'right' }}>{cfg.min_similarity}</span>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={cfg.min_similarity}
                onChange={e => setVal('min_similarity', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--vermilion)' }} />
              <div style={{ fontSize: 10, color: 'var(--ink-mute)', marginTop: -4 }}>越低召回越多，越高越精确</div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                <span style={{ fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)' }}>返回片段数 (top_k)</span>
                <span style={{ fontSize: 11, color: 'var(--vermilion)', minWidth: 18, textAlign: 'right' }}>{cfg.top_k}</span>
              </div>
              <input type="range" min="3" max="30" step="1" value={cfg.top_k}
                onChange={e => setVal('top_k', parseInt(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--vermilion)' }} />
              <div style={{ fontSize: 10, color: 'var(--ink-mute)', marginTop: -4 }}>越多上下文越全，但 LLM 调用更长</div>

              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--ink-soft)', fontFamily: 'var(--serif)', cursor: 'pointer', marginTop: 2 }}>
                <input type="checkbox" checked={cfg.enable_query_rewrite} onChange={e => setVal('enable_query_rewrite', e.target.checked)} />
                查询改写
              </label>
            </div>
            {dirty && (
              <button className="sidebar-btn" onClick={handleSave} style={{ width: '100%', marginTop: 8, fontSize: 12, color: 'var(--vermilion)', borderColor: 'var(--vermilion)' }}>
                应用设置
              </button>
            )}
          </div>
        )}

        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <ExportButton />
        </div>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <DocSection onOpenChunks={onOpenChunks} />
        </div>
      </div>
    </div>
  );
}
