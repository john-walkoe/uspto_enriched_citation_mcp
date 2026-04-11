"""MCP App HTML view for USPTO Enriched Citation search results."""

CITATION_RESULTS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USPTO Citation Results</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 13px; background: #f8f9fa; color: #1a1a2e; }

.header { background: #1a3a6b; color: #fff; padding: 10px 14px; display: flex; align-items: center; gap: 10px; }
.header h1 { font-size: 14px; font-weight: 600; }
.header .badge { background: #4a90d9; border-radius: 4px; padding: 2px 7px; font-size: 11px; }
.summary-bar { background: #e8f0fe; border-bottom: 1px solid #c5d8f7; padding: 7px 14px; font-size: 12px; color: #1a3a6b; display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.summary-bar span { font-weight: 600; }

/* ── Filter bar ── */
.filter-bar { background: #f4f7fd; border: 1px solid #c5d8f7; border-radius: 6px; margin: 8px 14px 0; padding: 7px 10px; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.filter-group { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.filter-label { font-size: 10px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; margin-right: 2px; white-space: nowrap; }
.filter-sep { width: 1px; background: #dde3ed; height: 18px; margin: 0 4px; align-self: center; }
.pill { border: 1px solid #c5d8f7; border-radius: 12px; padding: 2px 9px; font-size: 11px; font-weight: 700; cursor: pointer; background: #fff; color: #1a3a6b; transition: all 0.12s; user-select: none; }
.pill:hover { border-color: #4a90d9; background: #e8f0fe; }
.pill.active { background: #1a3a6b; color: #fff; border-color: #1a3a6b; }
.pill.active-X { background: #c0392b; color: #fff; border-color: #c0392b; }
.pill.active-Y { background: #e67e22; color: #fff; border-color: #e67e22; }
.pill.active-A { background: #27ae60; color: #fff; border-color: #27ae60; }
.pill-count { font-size: 9px; font-weight: 700; background: rgba(255,255,255,0.25); border-radius: 8px; padding: 0 4px; margin-left: 3px; }
.pill:not(.active) .pill-count { background: #e8f0fe; color: #1a3a6b; }
.filter-result { font-size: 11px; color: #888; margin-left: auto; }
.clear-link { font-size: 11px; color: #c0392b; cursor: pointer; text-decoration: underline; display: none; }

.container { padding: 10px 14px; }
.card { background: #fff; border: 1px solid #dde3ed; border-radius: 6px; margin-bottom: 8px; padding: 10px 12px; transition: opacity 0.1s; }
.card:hover { border-color: #4a90d9; box-shadow: 0 1px 4px rgba(74,144,217,0.15); }
.card.hidden { display: none; }
.card-header { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.card-title { font-weight: 600; font-size: 13px; flex: 1; }
.badges { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 5px; }

.badge-examiner { background: #1a3a6b; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600; }
.badge-applicant { background: #6c757d; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600; }
.badge-X { background: #c0392b; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }
.badge-Y { background: #e67e22; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }
.badge-A { background: #27ae60; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }
.badge-cat { background: #8e44ad; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }

.meta { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 4px 12px; font-size: 11px; color: #555; }
.meta-item { display: flex; flex-direction: column; }
.meta-label { color: #888; font-size: 10px; text-transform: uppercase; letter-spacing: 0.3px; }
.meta-val { color: #1a1a2e; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.passage { margin-top: 6px; background: #f0f4ff; border-left: 3px solid #4a90d9; padding: 4px 8px; font-size: 11px; color: #444; border-radius: 0 3px 3px 0; }
.pfw-link { margin-top: 6px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.pfw-btn { display: inline-block; background: #1a3a6b; color: #fff; border: none; border-radius: 4px; padding: 3px 9px; font-size: 11px; cursor: pointer; }
.pfw-btn:hover { background: #4a90d9; }
.gp-btn { display: inline-block; background: #4a90d9; color: #fff; border: none; border-radius: 4px; padding: 3px 9px; font-size: 11px; cursor: pointer; }
.gp-btn:hover { background: #1a3a6b; }

.no-match { text-align: center; padding: 20px; color: #888; font-size: 12px; display: none; }

#loading { text-align: center; padding: 30px; color: #666; }
#error { background: #fde8e8; border: 1px solid #f5c6cb; color: #721c24; padding: 10px 14px; margin: 10px 14px; border-radius: 4px; }
.login-note { background: #fff9e6; border-bottom: 1px solid #ffe08a; padding: 5px 14px; font-size: 11px; color: #6b5000; }
</style>
</head>
<body>
<div class="header">
  <h1>USPTO Enriched Citations</h1>
  <span class="badge" id="tier-badge">loading...</span>
</div>
<div class="summary-bar" id="summary-bar" style="display:none"></div>
<div class="login-note">Tip: "Open in Patent Center" links require a USPTO account — log in at <strong>patentcenter.uspto.gov</strong> first. Google Patents links open without login.</div>
<div class="filter-bar" id="filter-bar" style="display:none"></div>
<div id="loading">Loading citation results...</div>
<div id="error" style="display:none"></div>
<div class="container" id="content" style="display:none">
  <div id="cards"></div>
  <div class="no-match" id="no-match">No citations match the selected filters. <a href="#" onclick="clearFilters();return false;" style="color:#1a3a6b">Clear filters</a></div>
</div>

<script type="module">
import { App } from 'https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@1.2.0/dist/src/app-with-deps.js';

const app = new App({ name: 'USPTO Citation Results', version: '1.0.0' });

let allDocs = [];
let cardEls = [];                          // parallel array to allDocs
let activeFilters = {};                    // { source: 'examiner' | null, category: 'X' | null, oaType: 'CTNF' | null }

app.ontoolresult = (result) => {
  const text = result.content?.find(c => c.type === 'text')?.text;
  try { render(JSON.parse(text)); }
  catch { showError('Could not parse citation results.'); }
};

app.connect();

// ── Render ────────────────────────────────────────────────────────────────────

function render(data) {
  document.getElementById('loading').style.display = 'none';
  if (data.status === 'error' || data.error) { showError(data.error || data.message || 'API error'); return; }

  const resp = data.response || {};
  allDocs = resp.docs || [];
  activeFilters = {};

  const numFound = resp.numFound || 0;
  const start = resp.start || 0;
  const tier = data.query_info?.tier || 'minimal';

  document.getElementById('tier-badge').textContent = tier.toUpperCase();

  const examinerCount = allDocs.filter(d => d.examinerCitedReferenceIndicator).length;
  const withPassage = allDocs.filter(d => d.passageLocationText?.length).length;
  const summaryBar = document.getElementById('summary-bar');
  summaryBar.style.display = 'flex';
  summaryBar.innerHTML = `
    <div>Found: <span>${numFound.toLocaleString()}</span> citations</div>
    <div>Showing: <span>${start + 1}–${Math.min(start + allDocs.length, numFound)}</span></div>
    <div>Examiner-cited: <span>${examinerCount}</span></div>
    ${withPassage ? `<div>With passages: <span>${withPassage}</span></div>` : ''}
    ${data.query_info?.constructed_query ? `<div style="color:#888;font-size:11px;font-weight:400">Query: ${data.query_info.constructed_query.substring(0,80)}${data.query_info.constructed_query.length>80?'…':''}</div>` : ''}
  `;

  // Build cards DOM
  const cardsEl = document.getElementById('cards');
  cardsEl.innerHTML = '';
  cardEls = [];
  if (allDocs.length === 0) {
    cardsEl.innerHTML = '<div style="text-align:center;padding:24px;color:#888">No citations found.</div>';
  } else {
    allDocs.forEach(doc => {
      const el = buildCard(doc);
      cardsEl.appendChild(el);
      cardEls.push(el);
    });
  }

  buildFilterBar();
  document.getElementById('content').style.display = 'block';
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function googlePatentsUrl(id) {
  if (!id || id === '—') return null;
  // Only show for patent/publication identifiers starting with 2-letter country code
  // Excludes NPL references (journal articles, books, etc.)
  if (!/^[A-Z]{2}/.test(id)) return null;
  // Strip spaces, commas, slashes to build Google Patents identifier (e.g. "US 6,848,420 B2" → "US6848420B2")
  const clean = id.replace(/[\s,/]/g, '');
  return `https://patents.google.com/patent/${encodeURIComponent(clean)}`;
}

function formatPassages(passages) {
  if (!passages?.length) return '';
  const items = [];
  passages.forEach(p => {
    p.split('|').forEach(item => {
      const t = item.trim();
      if (t) items.push(t);
    });
  });
  return items.join(' · ');
}

// ── Card builder ──────────────────────────────────────────────────────────────

function categoryBadge(code) {
  if (!code) return '';
  const cls = ['X','Y','A'].includes(code) ? `badge-${code}` : 'badge-cat';
  const labels = { X: 'X — Novel', Y: 'Y — Inventive', A: 'A — Background' };
  return `<span class="${cls}">${labels[code] || code}</span>`;
}

function buildCard(doc) {
  const div = document.createElement('div');
  div.className = 'card';

  const catCode  = doc.citationCategoryCode || '';
  const isExam   = !!doc.examinerCitedReferenceIndicator;
  const oaCat    = doc.officeActionCategory || '';

  // Data attributes used for filtering
  div.dataset.source   = isExam ? 'examiner' : 'applicant';
  div.dataset.category = catCode;
  div.dataset.oatype   = oaCat;

  const citedId  = doc.citedDocumentIdentifier || doc.publicationNumber || '—';
  const appNum   = doc.patentApplicationNumber || '';
  const gpUrl    = googlePatentsUrl(citedId);
  const artUnit  = doc.groupArtUnitNumber || '—';
  const techCenter = doc.techCenter || '—';
  const oaDate   = doc.officeActionDate ? doc.officeActionDate.split('T')[0] : '—';
  const passages = doc.passageLocationText;
  const inventor = doc.inventorNameText || '';

  div.innerHTML = `
    <div class="card-header"><div class="card-title">${citedId}</div></div>
    <div class="badges">
      ${isExam ? '<span class="badge-examiner">EXAMINER CITED</span>' : '<span class="badge-applicant">APPLICANT CITED</span>'}
      ${categoryBadge(catCode)}
      ${oaCat ? `<span class="badge-cat">${oaCat}</span>` : ''}
    </div>
    <div class="meta">
      <div class="meta-item"><span class="meta-label">Application</span><span class="meta-val">${appNum || '—'}</span></div>
      <div class="meta-item"><span class="meta-label">Art Unit</span><span class="meta-val">${artUnit}</span></div>
      <div class="meta-item"><span class="meta-label">Tech Center</span><span class="meta-val">${techCenter}</span></div>
      <div class="meta-item"><span class="meta-label">OA Date</span><span class="meta-val">${oaDate}</span></div>
      ${inventor ? `<div class="meta-item"><span class="meta-label">Inventor / Author</span><span class="meta-val">${inventor}</span></div>` : ''}
      ${doc.relatedClaimNumberText ? `<div class="meta-item"><span class="meta-label">Claims</span><span class="meta-val">${doc.relatedClaimNumberText}</span></div>` : ''}
    </div>
    ${passages?.length ? `<div class="passage">📍 ${formatPassages(passages)}</div>` : ''}
    ${(appNum || gpUrl) ? `<div class="pfw-link">
      ${appNum ? `<button class="pfw-btn">Open in Patent Center →</button>` : ''}
      ${gpUrl ? `<button class="gp-btn">Google Patents →</button>` : ''}
    </div>` : ''}
  `;
  if (appNum) div.querySelector('.pfw-btn')?.addEventListener('click', () => app.openLink({ url: `https://patentcenter.uspto.gov/applications/${appNum}` }));
  if (gpUrl)  div.querySelector('.gp-btn')?.addEventListener('click',  () => app.openLink({ url: gpUrl }));
  return div;
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function buildFilterBar() {
  const bar = document.getElementById('filter-bar');
  if (allDocs.length < 2) { bar.style.display = 'none'; return; }

  // Collect unique values per dimension (only where values exist)
  const sources    = countBy(d => d.examinerCitedReferenceIndicator ? 'examiner' : 'applicant');
  const categories = countBy(d => d.citationCategoryCode, v => !!v);
  const oaTypes    = countBy(d => d.officeActionCategory, v => !!v);

  bar.style.display = 'flex';
  bar.innerHTML = '';

  if (Object.keys(sources).length > 1)
    bar.appendChild(pillGroup('Source', sources, 'source', {
      examiner: { label: 'Examiner', activeClass: 'active' },
      applicant: { label: 'Applicant', activeClass: 'active' }
    }));

  if (Object.keys(categories).length > 1) {
    if (bar.children.length) bar.appendChild(sep());
    bar.appendChild(pillGroup('Category', categories, 'category', {
      X: { label: 'X — Novel',      activeClass: 'active-X' },
      Y: { label: 'Y — Inventive',  activeClass: 'active-Y' },
      A: { label: 'A — Background', activeClass: 'active-A' }
    }));
  }

  if (Object.keys(oaTypes).length > 1) {
    if (bar.children.length) bar.appendChild(sep());
    bar.appendChild(pillGroup('OA Type', oaTypes, 'oatype', {}));
  }

  if (bar.children.length === 0) { bar.style.display = 'none'; return; }

  // Result counter + clear link
  const counter = document.createElement('span');
  counter.className = 'filter-result';
  counter.id = 'filter-result';
  bar.appendChild(counter);

  const clearLink = document.createElement('a');
  clearLink.className = 'clear-link';
  clearLink.id = 'clear-link';
  clearLink.textContent = '× Clear';
  clearLink.addEventListener('click', clearFilters);
  bar.appendChild(clearLink);

  updateCounter();
}

function pillGroup(label, counts, dim, styleMap) {
  const group = document.createElement('div');
  group.className = 'filter-group';
  group.innerHTML = `<span class="filter-label">${label}:</span>`;

  Object.entries(counts).sort((a,b) => b[1]-a[1]).forEach(([val, count]) => {
    const cfg = styleMap[val] || {};
    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.dataset.dim = dim;
    pill.dataset.val = val;
    pill.innerHTML = `${cfg.label || val}: <span class="pill-count">${count}</span>`;
    pill.addEventListener('click', () => toggleFilter(dim, val, cfg.activeClass || 'active', pill));
    group.appendChild(pill);
  });
  return group;
}

function sep() {
  const s = document.createElement('div');
  s.className = 'filter-sep';
  return s;
}

function countBy(fn, filterFn = () => true) {
  const map = {};
  allDocs.forEach(d => {
    const v = fn(d);
    if (filterFn(v)) map[v] = (map[v] || 0) + 1;
  });
  return map;
}

// ── Filter logic ──────────────────────────────────────────────────────────────

function toggleFilter(dim, val, activeClass, pillEl) {
  if (activeFilters[dim] === val) {
    // Deselect
    activeFilters[dim] = null;
    pillEl.classList.remove(activeClass);
  } else {
    // Deselect previous pill in same dimension
    document.querySelectorAll(`.pill[data-dim="${dim}"]`).forEach(p => {
      p.className = 'pill';   // reset all active classes
    });
    activeFilters[dim] = val;
    pillEl.classList.add(activeClass);
  }
  applyFilters();
}

function applyFilters() {
  let visible = 0;
  cardEls.forEach((el, i) => {
    const doc = allDocs[i];
    const src   = el.dataset.source;
    const cat   = el.dataset.category;
    const oat   = el.dataset.oatype;

    const show =
      (!activeFilters.source   || src === activeFilters.source) &&
      (!activeFilters.category || cat === activeFilters.category) &&
      (!activeFilters.oatype   || oat === activeFilters.oatype);

    el.classList.toggle('hidden', !show);
    if (show) visible++;
  });
  document.getElementById('no-match').style.display = visible === 0 ? 'block' : 'none';
  updateCounter();
}

function updateCounter() {
  const hasFilter = Object.values(activeFilters).some(Boolean);
  const counter = document.getElementById('filter-result');
  const clearEl = document.getElementById('clear-link');
  if (!counter) return;
  if (!hasFilter) {
    counter.textContent = '';
    if (clearEl) clearEl.style.display = 'none';
    return;
  }
  const visible = cardEls.filter(el => !el.classList.contains('hidden')).length;
  counter.textContent = `${visible} of ${allDocs.length} shown`;
  if (clearEl) clearEl.style.display = 'inline';
}

window.clearFilters = function() {
  activeFilters = {};
  document.querySelectorAll('.pill').forEach(p => p.className = 'pill');
  cardEls.forEach(el => el.classList.remove('hidden'));
  document.getElementById('no-match').style.display = 'none';
  updateCounter();
};

function showError(msg) {
  document.getElementById('loading').style.display = 'none';
  const el = document.getElementById('error');
  el.style.display = 'block';
  el.textContent = `Error: ${msg}`;
}
</script>
</body>
</html>"""
