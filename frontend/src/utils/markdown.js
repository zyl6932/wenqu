import { marked } from 'marked';

let configured = false;

function configure() {
  if (configured) return;
  marked.setOptions({ breaks: true, gfm: true });
  configured = true;
}

export function renderMarkdown(text) {
  if (!text) return '';
  configure();
  try {
    let html = marked.parse(text);
    html = html.replace(/<pre>/g, '<pre><button class="code-copy-btn">复制</button>');
    return html;
  } catch {
    return fallbackRender(text);
  }
}

function fallbackRender(text) {
  let html = escHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  return html;
}

export function escHtml(s) {
  const el = document.createElement('span');
  el.textContent = s;
  return el.innerHTML;
}

export function escAttr(s) {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
