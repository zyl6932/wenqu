import { marked } from 'marked';

let configured = false;

function configure() {
  if (configured) return;
  marked.use({ breaks: true, gfm: true });
  configured = true;
}

export function renderMarkdown(text) {
  if (!text) return '';
  configure();
  const html = marked.parse(text).replace(/<pre>/g, '<pre><button class="code-copy-btn">复制</button>');
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
