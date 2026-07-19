"""MCP App HTML view for registered-user management (admin tool)."""

USER_MANAGEMENT_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USPTO Citations MCP — Users</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 13px; background: #f8f9fa; color: #1a1a2e; }

.header { background: #4a1a6b; color: #fff; padding: 10px 14px; display: flex; justify-content: space-between; align-items: baseline; }
.header h1 { font-size: 14px; font-weight: 600; }
.header .count { font-size: 11px; opacity: .8; }
.container { padding: 12px 14px; }

.notice { background: #eef7ee; border: 1px solid #c9e5c9; color: #205020; padding: 8px 12px; border-radius: 4px; margin-bottom: 10px; font-size: 12px; }

.table { width: 100%; border-collapse: collapse; font-size: 12px; background: #fff; border: 1px solid #dde3ed; border-radius: 6px; overflow: hidden; }
.table th { background: #f0e8ff; color: #4a1a6b; text-align: left; padding: 6px 10px; font-size: 11px; border-bottom: 1px solid #dde3ed; text-transform: uppercase; letter-spacing: .4px; }
.table td { padding: 6px 10px; border-bottom: 1px solid #f0f0f0; }
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: #faf7ff; }

.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge.admin { background: #f0e8ff; color: #4a1a6b; }
.badge.user { background: #eef2f7; color: #445; }
.badge.active { background: #eef7ee; color: #205020; }
.badge.inactive { background: #fde8e8; color: #721c24; }

#loading { text-align: center; padding: 30px; color: #666; }
#error { background: #fde8e8; border: 1px solid #f5c6cb; color: #721c24; padding: 10px 14px; margin: 10px 14px; border-radius: 4px; display: none; }
.foot { font-size: 11px; color: #8a92a3; margin-top: 10px; }
</style>
</head>
<body>
<div class="header">
  <h1>Registered Users</h1>
  <div class="count" id="count"></div>
</div>
<div id="loading">Loading users...</div>
<div id="error"></div>
<div class="container" id="content" style="display:none"></div>

<script type="module">
import { App } from 'https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@1.2.0/dist/src/app-with-deps.js';

const app = new App({ name: 'USPTO Citations MCP Users', version: '1.0.0' });

app.ontoolresult = (result) => {
  const text = result.content?.find(c => c.type === 'text')?.text;
  try {
    render(JSON.parse(text));
  } catch {
    showError('Could not parse user list.');
  }
};

app.connect();

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function render(data) {
  document.getElementById('loading').style.display = 'none';

  if (data.error) {
    showError(data.error);
    return;
  }

  const container = document.getElementById('content');
  const users = data.users || [];
  document.getElementById('count').textContent =
    `${users.length} user${users.length === 1 ? '' : 's'}`;

  const notice = data.message
    ? `<div class="notice">${esc(data.message)}</div>` : '';

  const rows = users.map(u => `
    <tr>
      <td>${esc(u.email)}</td>
      <td><span class="badge ${u.role === 'admin' ? 'admin' : 'user'}">${esc(u.role)}</span></td>
      <td><span class="badge ${u.active ? 'active' : 'inactive'}">${u.active ? 'active' : 'inactive'}</span></td>
      <td>${u.last_login_at ? esc(u.last_login_at.substring(0, 16).replace('T', ' ')) + (u.last_login_idp ? ' · ' + esc(u.last_login_idp) : '') : '—'}</td>
      <td>${esc(u.display_name || '')}</td>
    </tr>`).join('');

  container.innerHTML = `${notice}
    <table class="table">
      <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Last sign-in</th><th>Name</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5">No registered users.</td></tr>'}</tbody>
    </table>
    <p class="foot">Changes to role or active status take effect at the user's
    next token refresh (up to 1 hour). Ask in chat to add, deactivate, or
    change the role of a user.</p>`;
  container.style.display = 'block';
}

function showError(msg) {
  document.getElementById('loading').style.display = 'none';
  const el = document.getElementById('error');
  el.textContent = msg;
  el.style.display = 'block';
}
</script>
</body>
</html>
"""
