import { useEffect } from 'react';
import { uploadFile } from '../api/client';

export function useDragDrop(onUploaded) {
  useEffect(() => {
    function onDragOver(e) { e.preventDefault(); document.body.style.opacity = '0.9'; }
    function onDragLeave() { document.body.style.opacity = ''; }
    async function onDrop(e) {
      e.preventDefault();
      document.body.style.opacity = '';
      const files = e.dataTransfer.files;
      if (!files.length) return;
      const fd = new FormData();
      for (const f of files) fd.append('file', f);
      try {
        const data = await uploadFile(fd);
        onUploaded?.(data.message || '上传完成');
      } catch {
        onUploaded?.('上传失败');
      }
    }
    document.addEventListener('dragover', onDragOver);
    document.addEventListener('dragleave', onDragLeave);
    document.addEventListener('drop', onDrop);
    return () => {
      document.removeEventListener('dragover', onDragOver);
      document.removeEventListener('dragleave', onDragLeave);
      document.removeEventListener('drop', onDrop);
    };
  }, [onUploaded]);
}
