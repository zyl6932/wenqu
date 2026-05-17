import React, { useState, useEffect } from 'react';
import Modal from './Modal';
import { fetchDocContent } from '../../api/client';

export default function DocModal({ path, onClose }) {
  const [content, setContent] = useState(null);
  const [name, setName] = useState('');

  useEffect(() => {
    if (!path) return;
    fetchDocContent(path).then(data => {
      if (data.error) setContent(data.error);
      else { setContent(data.content); setName(data.name); }
    }).catch(() => setContent('加载失败'));
  }, [path]);

  return (
    <Modal title={name || '加载中...'} onClose={onClose}>
      {content === null
        ? <div className="modal-loading">加载中...</div>
        : <pre>{content}</pre>
      }
    </Modal>
  );
}
