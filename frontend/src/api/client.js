const BASE = '';

function friendlyErr(err) {
  if (err.message === 'Failed to fetch') return new Error('无网络连接，请检查网络后重试');
  return err;
}

async function request(method, path, body, opts = {}) {
  try {
    const init = { method, headers: { 'Content-Type': 'application/json' }, ...opts };
    if (body && !init.body) init.body = JSON.stringify(body);
    const res = await fetch(`${BASE}${path}`, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok && data.error) {
      if (typeof data.error === 'string') throw new Error(data.error);
      if (data.error.message) throw new Error(data.error.message);
      throw new Error(`HTTP ${res.status}`);
    }
    return data;
  } catch (e) {
    throw friendlyErr(e);
  }
}

export function askStream(question, history, signal, onToken, onSources, onDone, onError) {
  const controller = new AbortController();
  const linkedSignal = signal || controller.signal;
  const timeoutId = setTimeout(() => controller.abort(), 120000);
  const startTime = performance.now();

  const run = async () => {
    try {
      const res = await fetch(`${BASE}/api/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history }),
        signal: linkedSignal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            else if (data.sources) onSources(data.sources);
            else if (data.error) onError(data.error);
          } catch {}
        }
      }
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
      onDone(elapsed);
    } catch (err) {
      if (err.name === 'AbortError') onDone(null, true);
      else onError(friendlyErr(err).message);
    } finally {
      clearTimeout(timeoutId);
    }
  };

  run();
  return () => controller.abort();
}

export const fetchDocs = (page = 1, pageSize = 50) =>
  request('GET', `/api/docs?page=${page}&page_size=${pageSize}`);

export const fetchDocContent = (path) =>
  request('GET', `/api/docs/content?path=${encodeURIComponent(path)}`);

export const deleteDoc = (path) =>
  request('DELETE', '/api/docs', { path });

export const importDocs = () =>
  request('POST', '/api/import');

export const fetchChunks = (source, page = 1, pageSize = 50) =>
  request('GET', `/api/chunks?source=${encodeURIComponent(source)}&page=${page}&page_size=${pageSize}`);

export const updateChunk = (id, text) =>
  request('PUT', '/api/chunks', { id, text });

export const deleteOneChunk = (id) =>
  request('DELETE', '/api/chunks', { id });

export const deleteChunks = (ids) =>
  request('DELETE', '/api/chunks', { ids });

export const splitChunk = (id, separator) =>
  request('POST', '/api/chunks/split', { id, separator });

export const mergeChunks = (ids) =>
  request('POST', '/api/chunks/merge', { ids });

export const sendFeedback = (question, contexts, helpful) =>
  request('POST', '/api/feedback', { question, contexts, helpful });

export async function uploadFile(formData) {
  const res = await fetch(`${BASE}/api/upload`, { method: 'POST', body: formData });
  return res.json();
}
