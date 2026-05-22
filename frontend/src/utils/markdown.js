import { marked } from 'marked';
import katex from 'katex';

let configured = false;

function configure() {
  if (configured) return;
  marked.use({ breaks: true, gfm: true });
  configured = true;
}

function renderLatex(html) {
  // 块级公式 $$...$$
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_, tex) => {
    try {
      return `<div class="math-block">${katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false })}</div>`;
    } catch {
      return `<div class="math-block">$${tex}$</div>`;
    }
  });
  // 行内公式 $...$
  html = html.replace(/\$(.+?)\$/g, (_, tex) => {
    try {
      // 避免匹配 $$
      if (tex.includes('$')) return `$${tex}$`;
      return katex.renderToString(tex.trim(), { throwOnError: false });
    } catch {
      return `$${tex}$`;
    }
  });
  return html;
}

export function renderMarkdown(text) {
  if (!text) return '';
  configure();
  let html = marked.parse(text);
  html = renderLatex(html);
  html = html.replace(/<pre>/g, '<pre><button class="code-copy-btn">复制</button>');
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
