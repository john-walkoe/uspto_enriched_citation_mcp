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

`googlePatentsUrl` and the three helpers under it are a HAND-WRITTEN MIRROR of
the Python link builder (`util/reference_key`, `util/citation_links`): the
button on a card and the row's own `cite_as` have to open the same document,
and until 2026-09-12 this one stripped spaces, commas and slashes only, so a
foreign or kind-coded identifier opened a 404. `tests/test_views_smoke.py`
runs both builders over the same identifiers to keep them in step.

Interpolated into each view's HTML template. Keep the string free of `{}`
braces that an f-string would have to double-escape: the views concatenate
this constant rather than formatting it, and it should stay that way.
"""

SHARED_VIEW_JS = r"""
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// A card's Google Patents link and the row's own `cite_as` must open the same
// document, so the next four helpers mirror util/reference_key (normalize_
// reference_key, foreign_country_prefix) and util/citation_links
// (google_patents_url). Stripping only spaces, commas and slashes left the
// hyphens and the kind code in the URL, so "WO-2010098305-A1",
// "US-20140248322-A1" and "DE-102004012346-A1" each 404ed (measured
// 2026-09-12) and a foreign identifier got no country prefix at all.
const REFERENCE_EDGE_PUNCTUATION = /^[()[\]{}"';:]+|[()[\]{}"';:]+$/g;
const REFERENCE_SEPARATORS = /[\s/\-,._]/g;
// An optional short series or country marker, then 5 to 13 digits.
const REFERENCE_KEY_SHAPE = /^[A-Z]{0,3}\d{5,13}$/;
const REFERENCE_COUNTRY = /^([A-Z]{2})\d{5,13}$/;
// The US shapes: an 11-digit publication, a 7 or 8 digit patent, or a series
// marker. A 5 or 6 digit key is deliberately not linked: it is as likely a
// page number out of a journal citation as a 19th-century patent.
const US_DOCUMENT_SHAPE = /^(?:\d{11}|\d{7,8}|RE\d{5,6}|D\d{5,7}|PP\d{4,6})$/;
// Two-letter markers that lead a key without being country codes.
const NOT_COUNTRY_PREFIXES = ['US', 'RE', 'PP'];
const MAX_PREFIX_TOKENS = 3;

function normalizeReferenceSpan(span) {
  const cleaned = String(span).toUpperCase()
    .replace(REFERENCE_EDGE_PUNCTUATION, '')
    .replace(REFERENCE_SEPARATORS, '')
    .replace(/^US(?=[0-9A-Z])/, '')
    .replace(/(\d)[A-Z]\d?$/, '$1');
  return REFERENCE_KEY_SHAPE.test(cleaned) ? cleaned : null;
}

function foreignCountryPrefix(key) {
  const found = key ? REFERENCE_COUNTRY.exec(key) : null;
  return (found && NOT_COUNTRY_PREFIXES.indexOf(found[1]) === -1) ? found[1] : null;
}

function referenceKey(id) {
  const tokens = String(id).trim().split(/\s+/).filter(Boolean);
  const spans = [String(id)];
  for (let n = MAX_PREFIX_TOKENS; n >= 1; n--) spans.push(tokens.slice(0, n).join(' '));
  for (const span of spans) {
    const key = normalizeReferenceSpan(span);
    if (key) return key;
  }
  // The OA lane also writes the inventor name FIRST ("GOTO K WO-2010098305-A1"),
  // so a TRAILING span is read as well, and only when it carries a country
  // code: a bare number at the end of prose is a page range or a year. Two
  // letters closed by a period are an abbreviation ("No. 12345678"), not a
  // country.
  for (let n = 1; n <= MAX_PREFIX_TOKENS; n++) {
    const span = tokens.slice(-n).join(' ');
    if (/^[A-Z]{2}\s*\./.test(span.toUpperCase().replace(/^[([{"']+/, ''))) continue;
    const key = normalizeReferenceSpan(span);
    if (key && foreignCountryPrefix(key)) return key;
  }
  return null;
}

function googlePatentsUrl(id) {
  if (!id) return null;
  const key = referenceKey(id);
  if (!key) return null;
  // A US key takes the `US` prefix back; a foreign key already carries its
  // country code and takes no prefix and no kind code. Anything else has no
  // verified public URL, non-patent literature included.
  if (US_DOCUMENT_SHAPE.test(key)) {
    return `https://patents.google.com/patent/US${encodeURIComponent(key)}`;
  }
  if (foreignCountryPrefix(key)) {
    return `https://patents.google.com/patent/${encodeURIComponent(key)}`;
  }
  return null;
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
