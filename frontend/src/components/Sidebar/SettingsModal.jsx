import React, { useState, useEffect } from 'react';
import ThemeToggle from './ThemeToggle';
import FontSizeControl from './FontSizeControl';
import ExportButton from './ExportButton';
import { fetchConfig, updateConfig } from '../../api/client';
import { useToast } from '../../context/ToastContext';

export default function SettingsModal({ visible, onClose }) {
  const [cfg, setCfg] = useState(null);
  const [dirty, setDirty] = useState(false);
  const { addToast } = useToast();
  const [useLocal, setUseLocal] = useState(() => localStorage.getItem('wenqu_use_local') === 'true');

  useEffect(() => {
    if (!visible) return;
    setUseLocal(localStorage.getItem('wenqu_use_local') === 'true');
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

  function toggleLocal() {
    const next = !useLocal;
    localStorage.setItem('wenqu_use_local', next);
    setUseLocal(next);
  }

  if (!visible) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={e => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h3>设置</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="settings-modal-body">
          <div className="settings-row">
            <span>主题</span>
            <ThemeToggle />
          </div>
          <div className="settings-row">
            <span>字号</span>
            <FontSizeControl />
          </div>
          <div className="settings-row">
            <span>LLM 模型</span>
            <button className="sidebar-btn" onClick={toggleLocal} style={{ width: 'auto', padding: '4px 10px', fontSize: 12 }}>
              {useLocal ? '本地' : '联网'}
            </button>
          </div>

          {cfg && (
            <div className="settings-section">
              <div className="settings-section-title">检索设置</div>
              <div className="settings-row">
                <span>相似度阈值</span>
                <span style={{ fontSize: 11, color: 'var(--vermilion)' }}>{cfg.min_similarity}</span>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={cfg.min_similarity}
                onChange={e => setVal('min_similarity', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--vermilion)' }} />
              <div className="settings-hint">越低召回越多，越高越精确</div>

              <div className="settings-row" style={{ marginTop: 10 }}>
                <span>返回片段数 (top_k)</span>
                <span style={{ fontSize: 11, color: 'var(--vermilion)' }}>{cfg.top_k}</span>
              </div>
              <input type="range" min="3" max="30" step="1" value={cfg.top_k}
                onChange={e => setVal('top_k', parseInt(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--vermilion)' }} />
              <div className="settings-hint">越多上下文越全，但 LLM 调用更长</div>

              <label className="settings-row" style={{ cursor: 'pointer', marginTop: 6 }}>
                <input type="checkbox" checked={cfg.enable_query_rewrite} onChange={e => setVal('enable_query_rewrite', e.target.checked)} />
                <span>查询改写</span>
              </label>

              {dirty && (
                <button className="sidebar-btn" onClick={handleSave} style={{ width: '100%', marginTop: 10, fontSize: 12, color: 'var(--vermilion)', borderColor: 'var(--vermilion)' }}>
                  应用设置
                </button>
              )}
            </div>
          )}

          <div className="settings-section">
            <ExportButton />
          </div>
        </div>
      </div>
    </div>
  );
}
