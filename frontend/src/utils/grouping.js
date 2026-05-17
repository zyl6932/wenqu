export function groupByTime(conversations) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 86400000;
  const week = today - 7 * 86400000;

  const groups = { today: [], yesterday: [], week: [], older: [] };
  conversations.forEach(c => {
    const d = c.createdAt || 0;
    if (d >= today) groups.today.push(c);
    else if (d >= yesterday) groups.yesterday.push(c);
    else if (d >= week) groups.week.push(c);
    else groups.older.push(c);
  });
  return { groups, labels: { today: '今天', yesterday: '昨天', week: '7天内', older: '更早' } };
}

export function escHtml(s) {
  const el = document.createElement('span');
  el.textContent = s;
  return el.innerHTML;
}

export function escAttr(s) {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
