"""MCP App HTML view for USPTO citation statistics and aggregations."""

STATISTICS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USPTO Citation Statistics</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 13px; background: #f8f9fa; color: #1a1a2e; }

.header { background: #4a1a6b; color: #fff; padding: 10px 14px; }
.header h1 { font-size: 14px; font-weight: 600; }
.container { padding: 12px 14px; }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin-bottom: 14px; }
.stat-card { background: #fff; border: 1px solid #dde3ed; border-radius: 6px; padding: 10px 12px; text-align: center; }
.stat-value { font-size: 22px; font-weight: 700; color: #4a1a6b; }
.stat-label { font-size: 11px; color: #888; margin-top: 2px; }

.section { background: #fff; border: 1px solid #dde3ed; border-radius: 6px; margin-bottom: 10px; padding: 10px 12px; }
.section-title { font-weight: 600; font-size: 12px; color: #4a1a6b; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.4px; }

.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.bar-label { min-width: 90px; font-size: 11px; color: #444; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 14px; background: #f0f0f0; border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; background: #4a1a6b; border-radius: 3px; transition: width 0.3s; }
.bar-count { min-width: 50px; font-size: 11px; color: #666; }

.table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table th { background: #f0e8ff; color: #4a1a6b; text-align: left; padding: 5px 8px; font-size: 11px; border-bottom: 1px solid #dde3ed; }
.table td { padding: 5px 8px; border-bottom: 1px solid #f0f0f0; }
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: #faf7ff; }

#loading { text-align: center; padding: 30px; color: #666; }
#error { background: #fde8e8; border: 1px solid #f5c6cb; color: #721c24; padding: 10px 14px; margin: 10px 14px; border-radius: 4px; }
</style>
</head>
<body>
<div class="header">
  <h1>USPTO Citation Statistics</h1>
</div>
<div id="loading">Loading statistics...</div>
<div id="error" style="display:none"></div>
<div class="container" id="content" style="display:none"></div>

<script type="module">
import { App } from 'https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@1.2.0/dist/src/app-with-deps.js';

const app = new App({ name: 'USPTO Citation Statistics', version: '1.0.0' });

app.ontoolresult = (result) => {
  const text = result.content?.find(c => c.type === 'text')?.text;
  try {
    render(JSON.parse(text));
  } catch {
    showError('Could not parse statistics results.');
  }
};

app.connect();

function render(data) {
  document.getElementById('loading').style.display = 'none';

  if (data.status === 'error' || data.error) {
    showError(data.error || data.message || 'API returned an error.');
    return;
  }

  const container = document.getElementById('content');
  container.innerHTML = '';

  // Summary cards
  const total = data.total_citations || data.total_found || data.response?.numFound || 0;
  const summaryHtml = `
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-value">${total.toLocaleString()}</div><div class="stat-label">Total Matching</div></div>
      ${data.examiner_cited_count !== undefined ? `<div class="stat-card"><div class="stat-value">${(data.examiner_cited_count||0).toLocaleString()}</div><div class="stat-label">Examiner Cited</div></div>` : ''}
      ${data.applicant_cited_count !== undefined ? `<div class="stat-card"><div class="stat-value">${(data.applicant_cited_count||0).toLocaleString()}</div><div class="stat-label">Applicant Cited</div></div>` : ''}
      ${data.unique_applications !== undefined ? `<div class="stat-card"><div class="stat-value">${(data.unique_applications||0).toLocaleString()}</div><div class="stat-label">Unique Apps</div></div>` : ''}
    </div>`;
  container.innerHTML += summaryHtml;

  // Breakdowns
  const breakdowns = data.breakdowns || data.aggregations || {};
  for (const [field, counts] of Object.entries(breakdowns)) {
    if (!counts || typeof counts !== 'object') continue;
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 15);
    if (entries.length === 0) continue;
    const maxVal = entries[0][1] || 1;

    const rows = entries.map(([label, count]) => {
      const pct = Math.round((count / maxVal) * 100);
      return `<div class="bar-row">
        <div class="bar-label" title="${label}">${label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="bar-count">${count.toLocaleString()}</div>
      </div>`;
    }).join('');

    container.innerHTML += `
      <div class="section">
        <div class="section-title">${field.replace(/([A-Z])/g, ' $1').trim()}</div>
        ${rows}
      </div>`;
  }

  // Sample docs table if present
  const docs = data.response?.docs || data.sample_docs || [];
  if (docs.length > 0 && !data.breakdowns) {
    const keys = Object.keys(docs[0]).filter(k => !k.startsWith('_')).slice(0, 6);
    const headerRow = keys.map(k => `<th>${k}</th>`).join('');
    const bodyRows = docs.slice(0, 10).map(doc => {
      const cells = keys.map(k => {
        const v = doc[k];
        const display = Array.isArray(v) ? v[0]?.substring(0,40) : String(v||'').substring(0,40);
        return `<td title="${String(v||'')}">${display}</td>`;
      }).join('');
      return `<tr>${cells}</tr>`;
    }).join('');
    container.innerHTML += `
      <div class="section">
        <div class="section-title">Sample Records (${docs.length})</div>
        <table class="table"><thead><tr>${headerRow}</tr></thead><tbody>${bodyRows}</tbody></table>
      </div>`;
  }

  // Fallback for raw JSON
  if (container.innerHTML.trim() === '') {
    container.innerHTML = `<pre style="font-size:11px;white-space:pre-wrap;word-break:break-all">${JSON.stringify(data, null, 2)}</pre>`;
  }

  document.getElementById('content').style.display = 'block';
}

function showError(msg) {
  document.getElementById('loading').style.display = 'none';
  const el = document.getElementById('error');
  el.style.display = 'block';
  el.textContent = `Error: ${msg}`;
}
</script>
</body>
</html>"""
