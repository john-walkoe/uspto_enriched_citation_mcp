"""MCP App HTML view for USPTO Office Action Citations (v2) search results."""

OA_CITATIONS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USPTO OA Citations</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 13px; background: #f8f9fa; color: #1a1a2e; }

.header { background: #2d4a22; color: #fff; padding: 10px 14px; display: flex; align-items: center; gap: 10px; }
.header h1 { font-size: 14px; font-weight: 600; }
.header .badge { background: #5a8a3a; border-radius: 4px; padding: 2px 7px; font-size: 11px; }
.summary-bar { background: #eef6e8; border-bottom: 1px solid #c3ddb3; padding: 7px 14px; font-size: 12px; color: #2d4a22; display: flex; gap: 16px; flex-wrap: wrap; }
.summary-bar span { font-weight: 600; }

/* Filter bar */
.filter-bar { background: #f4f8f1; border: 1px solid #b8d4a0; border-radius: 6px; margin: 8px 14px 0; padding: 7px 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-height: 36px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.filter-group { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.filter-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; color: #5a7a50; margin-right: 2px; }
.filter-sep { width: 1px; height: 18px; background: #c3ddb3; margin: 0 4px; }
.filter-result { font-size: 11px; color: #5a7a50; margin-left: auto; }
.clear-link { font-size: 11px; color: #c0392b; cursor: pointer; text-decoration: underline; display: none; }
.pill {
  display: inline-flex; align-items: center; gap: 4px;
  background: #fff; border: 1px solid #b8d4a0; border-radius: 12px;
  padding: 2px 9px; font-size: 11px; font-weight: 700; cursor: pointer;
  transition: background 0.1s, border-color 0.1s; color: #2d4a22;
}
.pill:hover { background: #e8f4dc; border-color: #5a8a3a; }
.pill.active { background: #2d4a22; color: #fff; border-color: #2d4a22; }
.pill.active-102 { background: #c0392b; color: #fff; border-color: #c0392b; }
.pill.active-103 { background: #d35400; color: #fff; border-color: #d35400; }
.pill.active-112 { background: #8e44ad; color: #fff; border-color: #8e44ad; }
.pill-count { font-size: 10px; font-weight: 700; opacity: 0.9; }

.container { padding: 10px 14px; }
.card { background: #fff; border: 1px solid #dde3ed; border-radius: 6px; margin-bottom: 8px; padding: 10px 12px; }
.card:hover { border-color: #5a8a3a; box-shadow: 0 1px 4px rgba(90,138,58,0.15); }
.card.hidden { display: none; }
.badges { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }

.badge-examiner { background: #2d4a22; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600; }
.badge-applicant { background: #6c757d; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600; }
.badge-oa { background: #5a8a3a; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }
.badge-legal { background: #8e44ad; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600; }
.badge-action { background: #c0392b; color: #fff; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }

.meta { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 4px 12px; font-size: 11px; color: #555; }
.meta-item { display: flex; flex-direction: column; }
.meta-label { color: #888; font-size: 10px; text-transform: uppercase; letter-spacing: 0.3px; }
.meta-val { color: #1a1a2e; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.pfw-link { margin-top: 6px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.pfw-btn { display: inline-block; background: #2d4a22; color: #fff; border: none; border-radius: 4px; padding: 3px 9px; font-size: 11px; cursor: pointer; }
.pfw-btn:hover { background: #5a8a3a; }
.gp-btn { display: inline-block; background: #4a90d9; color: #fff; border: none; border-radius: 4px; padding: 3px 9px; font-size: 11px; cursor: pointer; }
.gp-btn:hover { background: #1a3a6b; }

#loading { text-align: center; padding: 30px; color: #666; }
#error { background: #fde8e8; border: 1px solid #f5c6cb; color: #721c24; padding: 10px 14px; margin: 10px 14px; border-radius: 4px; }
.note { background: #fff9e6; border: 1px solid #ffe08a; border-radius: 4px; padding: 7px 12px; margin-bottom: 8px; font-size: 11px; color: #6b5000; }
.login-note { background: #fff9e6; border-bottom: 1px solid #ffe08a; padding: 5px 14px; font-size: 11px; color: #6b5000; }
.no-match { text-align: center; padding: 24px; color: #888; display: none; }
.no-match a { color: #5a8a3a; cursor: pointer; text-decoration: underline; }
</style>
</head>
<body>
<div class="header">
  <h1>USPTO OA Citations (v2)</h1>
  <span class="badge" id="tier-badge">loading...</span>
</div>
<div class="summary-bar" id="summary-bar" style="display:none"></div>
<div class="login-note">Tip: "Open in Patent Center" links require a USPTO account — log in at <strong>patentcenter.uspto.gov</strong> first. Google Patents links open without login.</div>
<div class="filter-bar" id="filter-bar" style="display:none"></div>
<div id="loading">Loading OA Citation results...</div>
<div id="error" style="display:none"></div>
<div class="container" id="content" style="display:none">
  <div class="note">OA Citations v2 — raw citation data from Form 892 (examiner) and Form 1449 (applicant). For AI-enriched data with passage locations and claim mapping, use Enriched Citations.</div>
  <div id="cards"></div>
  <div class="no-match" id="no-match">No citations match the active filters. <a onclick="clearFilters()">Clear filters</a></div>
</div>

<script type="module">
import { App } from 'https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@1.2.0/dist/src/app-with-deps.js';

const app = new App({ name: 'USPTO OA Citations', version: '1.0.0' });

// Filter state: one active value per dimension (null = no filter)
const filters = { source: null, legal: null, action: null };

app.ontoolresult = (result) => {
  const text = result.content?.find(c => c.type === 'text')?.text;
  try {
    render(JSON.parse(text));
  } catch {
    showError('Could not parse OA citation results.');
  }
};

app.connect();

function render(data) {
  document.getElementById('loading').style.display = 'none';

  if (data.status === 'error' || data.error) {
    showError(data.error || data.message || 'API returned an error.');
    return;
  }

  const resp = data.response || {};
  const docs = resp.docs || [];
  const numFound = resp.numFound || 0;
  const start = resp.start || 0;
  const tier = data.query_info?.tier || 'minimal';

  document.getElementById('tier-badge').textContent = `OA v2 · ${tier.toUpperCase()}`;

  const examinerCount = docs.filter(d => d.examinerCitedReferenceIndicator).length;
  const summaryBar = document.getElementById('summary-bar');
  summaryBar.style.display = 'flex';
  summaryBar.innerHTML = `
    <div>Found: <span>${numFound.toLocaleString()}</span> citations</div>
    <div>Showing: <span>${start + 1}–${Math.min(start + docs.length, numFound)}</span></div>
    <div>Examiner-cited: <span>${examinerCount}</span></div>
  `;

  const cardsEl = document.getElementById('cards');
  cardsEl.innerHTML = '';
  if (docs.length === 0) {
    cardsEl.innerHTML = '<div style="text-align:center;padding:24px;color:#888">No OA citations found.</div>';
  } else {
    docs.forEach(doc => cardsEl.appendChild(buildCard(doc)));
    buildFilterBar(docs);
  }
  document.getElementById('content').style.display = 'block';
}

function googlePatentsUrl(id) {
  if (!id || id === '—') return null;
  // Only show for patent/publication identifiers starting with 2-letter country code
  // Excludes NPL references (journal articles, books, etc.)
  if (!/^[A-Z]{2}/.test(id)) return null;
  // Strip spaces, commas, slashes to build Google Patents identifier (e.g. "US 6,848,420 B2" → "US6848420B2")
  const clean = id.replace(/[\s,/]/g, '');
  return `https://patents.google.com/patent/${encodeURIComponent(clean)}`;
}

function buildCard(doc) {
  const div = document.createElement('div');
  div.className = 'card';

  const refId  = doc.referenceIdentifier || doc.parsedReferenceIdentifier || '—';
  const appNum = doc.patentApplicationNumber || '';
  const gpUrl  = googlePatentsUrl(refId);
  const artUnit = doc.groupArtUnitNumber || '—';
  const techCenter = doc.techCenter || '—';
  const actionType = doc.actionTypeCategory || '';
  const legalCode = doc.legalSectionCode || '';
  const isExaminer = doc.examinerCitedReferenceIndicator;
  const isApplicantOA = doc.applicantCitedExaminerReferenceIndicator;
  const isOACite = doc.officeActionCitationReferenceIndicator;
  const para = doc.paragraphNumber || '';
  const workGroup = doc.workGroup || '';
  const created = doc.createDateTime ? doc.createDateTime.split('T')[0] : '—';

  // Data attributes for filtering
  div.dataset.source = isExaminer ? 'examiner' : (isApplicantOA ? 'applicant' : 'other');
  div.dataset.legal = legalCode ? legalCode.replace(/\s+/g, '') : '';
  div.dataset.action = actionType.toLowerCase().replace(/\s+/g, '-');

  div.innerHTML = `
    <div style="font-weight:600;font-size:13px;margin-bottom:5px">${refId}</div>
    <div class="badges">
      ${isExaminer ? '<span class="badge-examiner">EXAMINER (892)</span>' : ''}
      ${isApplicantOA ? '<span class="badge-applicant">APPLICANT (1449)</span>' : ''}
      ${isOACite ? '<span class="badge-oa">IN OA</span>' : ''}
      ${actionType ? `<span class="badge-action">${actionType}</span>` : ''}
      ${legalCode ? `<span class="badge-legal">§ ${legalCode}</span>` : ''}
    </div>
    <div class="meta">
      <div class="meta-item"><span class="meta-label">Application</span><span class="meta-val">${appNum || '—'}</span></div>
      <div class="meta-item"><span class="meta-label">Art Unit</span><span class="meta-val">${artUnit}</span></div>
      <div class="meta-item"><span class="meta-label">Tech Center</span><span class="meta-val">${techCenter}</span></div>
      ${workGroup ? `<div class="meta-item"><span class="meta-label">Work Group</span><span class="meta-val">${workGroup}</span></div>` : ''}
      ${para ? `<div class="meta-item"><span class="meta-label">Paragraph</span><span class="meta-val">${para}</span></div>` : ''}
      <div class="meta-item"><span class="meta-label">Created</span><span class="meta-val">${created}</span></div>
    </div>
    ${(appNum || gpUrl) ? `<div class="pfw-link">
      ${appNum ? `<button class="pfw-btn">Open in Patent Center →</button>` : ''}
      ${gpUrl ? `<button class="gp-btn">Google Patents →</button>` : ''}
    </div>` : ''}
  `;

  if (appNum) div.querySelector('.pfw-btn')?.addEventListener('click', () => app.openLink({ url: `https://patentcenter.uspto.gov/applications/${appNum}` }));
  if (gpUrl)  div.querySelector('.gp-btn')?.addEventListener('click',  () => app.openLink({ url: gpUrl }));

  return div;
}

// ── Filter bar ───────────────────────────────────────────────────────────────

function buildFilterBar(docs) {
  const bar = document.getElementById('filter-bar');
  bar.innerHTML = '';

  // Count per source value
  const sourceCounts = countBy(d => d.dataset.source, () => true);
  // Count per legal section code
  const legalCounts = countBy(d => d.dataset.legal, d => d.dataset.legal !== '');
  // Count per action type
  const actionCounts = countBy(d => d.dataset.action, d => d.dataset.action !== '');

  let hasAny = false;

  // Source group: Examiner / Applicant
  const sourceStyleMap = {
    examiner: { label: 'Examiner (892)', activeClass: 'active' },
    applicant: { label: 'Applicant (1449)', activeClass: 'active' },
  };
  if (Object.keys(sourceCounts).length > 1) {
    bar.appendChild(pillGroup('Source', sourceCounts, 'source', sourceStyleMap));
    hasAny = true;
  }

  // § Legal section group
  const legalStyleMap = {
    '102': { label: '§ 102', activeClass: 'active-102' },
    '103': { label: '§ 103', activeClass: 'active-103' },
    '112': { label: '§ 112', activeClass: 'active-112' },
  };
  if (Object.keys(legalCounts).length > 1) {
    if (hasAny) bar.appendChild(sep());
    bar.appendChild(pillGroup('§ Code', legalCounts, 'legal', legalStyleMap));
    hasAny = true;
  }

  // Action type group
  if (Object.keys(actionCounts).length > 1) {
    if (hasAny) bar.appendChild(sep());
    bar.appendChild(pillGroup('Action', actionCounts, 'action', {}));
    hasAny = true;
  }

  if (hasAny) {
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

    bar.style.display = 'flex';
    updateCounter();
  }
}

function pillGroup(label, counts, dim, styleMap) {
  const group = document.createElement('div');
  group.className = 'filter-group';

  const lbl = document.createElement('span');
  lbl.className = 'filter-label';
  lbl.textContent = label;
  group.appendChild(lbl);

  // Sort: known codes first (102, 103, 112), then alphabetical
  const knownOrder = ['examiner', 'applicant', '102', '103', '112'];
  const sorted = Object.keys(counts).sort((a, b) => {
    const ia = knownOrder.indexOf(a), ib = knownOrder.indexOf(b);
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return a.localeCompare(b);
  });

  sorted.forEach(val => {
    const info = styleMap[val] || {};
    const displayLabel = info.label || val;
    const activeClass = info.activeClass || 'active';
    const count = counts[val];

    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.dataset.dim = dim;
    pill.dataset.val = val;
    pill.dataset.activeClass = activeClass;
    pill.innerHTML = `${displayLabel}: <span class="pill-count">${count}</span>`;
    pill.addEventListener('click', () => toggleFilter(dim, val, activeClass, pill));
    group.appendChild(pill);
  });

  return group;
}

function sep() {
  const s = document.createElement('div');
  s.className = 'filter-sep';
  return s;
}

function countBy(fn, filterFn) {
  const cards = Array.from(document.querySelectorAll('#cards .card'));
  const counts = {};
  cards.filter(filterFn).forEach(card => {
    const key = fn(card);
    if (key) counts[key] = (counts[key] || 0) + 1;
  });
  return counts;
}

function toggleFilter(dim, val, activeClass, pillEl) {
  // Deselect if already active
  if (filters[dim] === val) {
    filters[dim] = null;
    pillEl.classList.remove(activeClass);
  } else {
    // Deselect previous pill in this group
    if (filters[dim] !== null) {
      const prev = document.querySelector(`.pill[data-dim="${dim}"][data-val="${filters[dim]}"]`);
      if (prev) prev.classList.remove(prev.dataset.activeClass);
    }
    filters[dim] = val;
    pillEl.classList.add(activeClass);
  }
  applyFilters();
}

function applyFilters() {
  const cards = document.querySelectorAll('#cards .card');
  let visible = 0;
  cards.forEach(card => {
    const sourceOk = !filters.source || card.dataset.source === filters.source;
    const legalOk  = !filters.legal  || card.dataset.legal === filters.legal;
    const actionOk = !filters.action || card.dataset.action === filters.action;
    const show = sourceOk && legalOk && actionOk;
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  });
  updateCounter(visible, cards.length);
  document.getElementById('no-match').style.display = visible === 0 ? 'block' : 'none';
}

function updateCounter(visible, total) {
  const el = document.getElementById('filter-result');
  const clearEl = document.getElementById('clear-link');
  if (!el) return;
  const hasFilter = Object.values(filters).some(v => v !== null);
  if (!hasFilter) {
    el.textContent = '';
    if (clearEl) clearEl.style.display = 'none';
    return;
  }
  if (visible === undefined) {
    const cards = document.querySelectorAll('#cards .card');
    visible = Array.from(cards).filter(c => !c.classList.contains('hidden')).length;
    total = cards.length;
  }
  el.textContent = `${visible} of ${total} shown`;
  if (clearEl) clearEl.style.display = 'inline';
}

window.clearFilters = function() {
  filters.source = null;
  filters.legal = null;
  filters.action = null;
  document.querySelectorAll('.pill.active, .pill.active-102, .pill.active-103, .pill.active-112').forEach(p => {
    p.classList.remove('active', 'active-102', 'active-103', 'active-112');
  });
  document.querySelectorAll('#cards .card').forEach(c => c.classList.remove('hidden'));
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
