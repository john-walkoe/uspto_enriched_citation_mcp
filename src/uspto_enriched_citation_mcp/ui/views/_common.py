"""JavaScript shared byte-for-byte by the two MCP App card views.

`citation_results_view.py` and `oa_citations_view.py` were built by copy and
edit, and four helpers were identical in both: a styling or escaping fix had
to be applied twice and the pair had already drifted elsewhere (D-3). Only
the genuinely identical functions live here. `pillGroup`, `countBy`,
`toggleFilter` and `applyFilters` LOOK duplicated but are not: the OA view's
counters read the rendered DOM cards while the enriched view's read the
in-memory `allDocs` array, so folding them together would change behavior in
one of the two, which is exactly the kind of change a duplication cleanup
must not smuggle in.

Interpolated into each view's HTML template. Keep the string free of `{}`
braces that an f-string would have to double-escape: the views concatenate
this constant rather than formatting it, and it should stay that way.
"""

SHARED_VIEW_JS = r"""
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
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

function sep() {
  const s = document.createElement('div');
  s.className = 'filter-sep';
  return s;
}

function showError(msg) {
  document.getElementById('loading').style.display = 'none';
  const el = document.getElementById('error');
  el.style.display = 'block';
  el.textContent = `Error: ${msg}`;
}
"""
