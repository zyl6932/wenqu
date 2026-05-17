import React from 'react';
import { useToast } from '../../context/ToastContext';

export default function ToastContainer() {
  const { toasts } = useToast();
  if (!toasts.length) return null;
  return (
    <div id="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>{t.message}</div>
      ))}
    </div>
  );
}
