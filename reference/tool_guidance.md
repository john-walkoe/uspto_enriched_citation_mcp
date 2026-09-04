# USPTO Enriched Citation MCP — Tool Guidance

⚠️ **DEPRECATION NOTICE**: This file is auto-loaded by `tool_reflections.py`. Editing this file updates guidance without touching Python code.

---

## overview

## Available Sections and Quick Reference

### 🎯 Quick Reference Chart - What section for your question?

- 🔍 **"Find citations by examiner/application/tech"** → `fields`
- 🔀 **"Which lane — OA citations or enriched citations?"** → `oa_citations`
- 📄 **"Understand citation categories (X/Y/A)"** → `citation_codes`
- 🔖 **"Citation date coverage per lane"** → `data_coverage`
- 🤝 **"PFW workflow for office action documents"** → `workflows_pfw`
- 🚩 **"PTAB citation correlation"** → `workflows_ptab`
- 📊 **"FPD petition citation patterns"** → `workflows_fpd`
- 🏢 **"Complete lifecycle analysis"** → `workflows_complete`
- ⚙️ **"Tool guidance and parameters"** → `tools`
- ❌ **"Search errors or query issues"** → `errors`
- 💰 **"Reduce API costs and optimize"** → `cost`

### Two Citation Surfaces — Read This First

This MCP serves **two different USPTO indexes**. They are not tiers of the same
data and they do not share a field vocabulary:

| | **OA Citations (v2)** | **Enriched Citations (v3)** |
|---|---|---|
| Tools | `Citations_search_oa_citations_minimal` / `_balanced`, `Citations_get_oa_citation_fields` | `Citations_search_citations_minimal` / `_balanced`, `Citations_get_citation_details`, `Citations_get_citation_statistics`, `Citations_get_available_fields` |
| What it is | Raw citation lists transcribed from Form PTO-892 (examiner) and PTO-1449 (applicant IDS) | AI-extracted analysis of a subset of office actions |
| Documented window | Office actions 2017-10-01 → T-30d | Office actions 2017-10-01 → T-30d (same) |
| Adds | Statutory basis (`legalSectionCode` 102/103/112), rejection posture (`actionTypeCategory`), paragraph number | Passage locations, claim mapping, quality score, NPL flag, `officeActionDate` |
| Date filtering | **None** — no office-action date field exists | Full `officeActionDate` range queries |

**Routing rule: TRY BOTH.** Neither lane is a superset of the other — OA is
usually broader in bulk, but on a given application the enriched lane can
return more. For any completeness-sensitive question, query both and union.
Go single-lane only for a lane-exclusive capability: passage locations and
claim mapping → enriched; `legalSectionCode` statutory filter → OA.
Both lanes have also been observed serving records older than the documented
window. Full detail and measured numbers: `oa_citations` section.

### Available Sections:
- **overview**: Available sections and tool summary (this section)
- **oa_citations**: OA (v2) vs enriched (v3) routing rule, measured coverage, field matrix
- **workflows_pfw**: Citation + PFW integration workflows
- **workflows_ptab**: Citation + PTAB integration workflows
- **workflows_fpd**: Citation + FPD integration workflows
- **workflows_complete**: Four-MCP complete lifecycle analysis
- **citation_codes**: X/Y/A category decoder and NPL query guidance (use nplIndicator:true)
- **data_coverage**: per-lane date coverage and date handling
- **fields**: Field selection strategies and Solr/Lucene syntax
- **tools**: Tool-specific guidance and parameters
- **errors**: Common error patterns and troubleshooting
- **cost**: Cost optimization strategies

### Context Efficiency Benefits:
- **90-95% token reduction** (1-12KB per section vs 62KB total)
- **Targeted guidance** for specific workflows
- **Same comprehensive content** organized for efficiency
- **Consistent experience** across all USPTO MCPs

---

## tools

## Core Tools Overview

### Tool Inventory (10 tools, with defer_loading status)

Always loaded (defer_loading false): `Citations_get_guidance`,
`Citations_search_citations_minimal`, `Citations_search_oa_citations_minimal`.
Loaded on demand via tool search (defer_loading true):
`Citations_search_citations_balanced`, `Citations_get_citation_details`,
`Citations_get_citation_statistics`, `Citations_get_available_fields`,
`Citations_validate_query`, `Citations_search_oa_citations_balanced`,
`Citations_get_oa_citation_fields`. (An 11th tool, `citations_manage_users`,
registers only on OAuth deployments with user management enabled.)
Note: defer_loading is advisory metadata; each client decides which tools it
surfaces eagerly.

**Citations_get_guidance** - This Guidance Document
- **Purpose**: Sectioned workflow guidance (this document); pass `section` for one topic
- **Use Cases**: Workflow routing, coverage notes, cross-MCP integration patterns

### Enriched Citations Search Tools (v3, Progressive Disclosure)

**Citations_search_citations_minimal** - Citation Discovery
- **Purpose**: Fast citation discovery with essential fields (90-95% context reduction)
- **Use Cases**: Initial research, volume citation analysis, pattern identification
- **Fields**: Core identifiers, citation categories, art units, temporal data (8 fields)
- **Ultra-Minimal Mode**: Custom fields parameter for 99% reduction (2-3 fields only)
- **Recommended**: 50-100 results for discovery workflow
- **Date Range**: documented 2017-10-01+; older records observed in practice (see `data_coverage`)

**Citations_search_citations_balanced** - Detailed Citation Analysis
- **Purpose**: Comprehensive citation analysis with full context (70-80% context reduction)
- **Use Cases**: Detailed analysis, cross-MCP integration, legal research
- **Fields**: All citation metadata, classifications, cross-reference data (18 fields)
- **Ultra-Minimal Mode**: Custom fields parameter for 99% reduction (2-3 fields only)
- **Recommended**: 20-50 results for analysis workflow
- **Convenience params**: `patent_number` (granted patent number → crosswalked to
  `patentApplicationNumber`; 11-digit publication number → `publicationNumber`),
  `application_number`, `art_unit`, `tech_center`, `category_code`, `examiner_cited`,
  `date_start`/`date_end`

### OA Citations Search Tools (v2, Raw 892/1449 Lists)

**Citations_search_oa_citations_minimal** - Raw Citation Discovery
- **Purpose**: Complete cited-art inventory from the raw examiner/applicant forms
- **Use Cases**: Coverage sweeps, statutory-basis analysis, applicant-IDS inventory
- **Fields**: 7 key fields — application, art unit, tech center, `referenceIdentifier`,
  `actionTypeCategory`, `examinerCitedReferenceIndicator`, `createDateTime`
- **Convenience params**: `application_number`, `patent_number` (granted patent number,
  crosswalked to the application serial), `art_unit`, `tech_center`, `examiner_cited`
- **⚠️ No date filtering** — the index has no office-action date field

**Citations_search_oa_citations_balanced** - Full OA Detail
- **Purpose**: All 16 OA fields for selected applications
- **Adds over minimal**: `legalSectionCode` (102/103/112), `paragraphNumber`,
  `parsedReferenceIdentifier`, `applicantCitedExaminerReferenceIndicator`,
  `officeActionCitationReferenceIndicator`, `workGroup`

**Citations_get_oa_citation_fields** - OA Field Discovery
- **Purpose**: The 16 searchable OA v2 field names (a *different* vocabulary
  from enriched — always check before writing OA criteria)

### Detail Tools

**Citations_get_citation_details** - Full Citation Record
- **Purpose**: Complete citation details with optional citing context
- **Use Cases**: Specific citation analysis, passage examination, full record retrieval
- **Features**: Citation passage analysis, decision context, outcome verification
- **⚠️ IMPORTANT**: Returns citation METADATA only, NOT actual documents

**Citations_get_available_fields** - Field Discovery
- **Purpose**: Discover searchable field names and query syntax
- **Use Cases**: Query construction, field validation, syntax learning

**Citations_validate_query** - Query Optimization
- **Purpose**: Validate Solr/Lucene syntax and get optimization suggestions
- **Use Cases**: Query debugging, performance optimization, syntax learning

**Citations_get_citation_statistics** - Statistical Analysis
- **Purpose**: Get database statistics and aggregations
- **Use Cases**: Volume analysis, trend identification, strategic planning

### Progressive Disclosure Strategy

**Stage 0: Decide how many lanes (do this first)**
- **Default: BOTH.** Any completeness-sensitive question — full cited-art
  inventory, litigation sweeps, art-unit or examiner behavior, "was X ever
  cited" — runs both lanes and unions the results. Neither is a superset.
- Single-lane shortcut only for a lane-exclusive need: *"why was it cited /
  which claim / what passage"* or a date-windowed query → **enriched**;
  *"which references drew a §103"* → **OA** (`legalSectionCode`).
- Report both counts whenever you ran both, and say which lane gave what.
  See `oa_citations`.

**Stage 1: Discovery (Minimal Search) — run both**
- OA lane: `Citations_search_oa_citations_minimal` — raw 892/1449 inventory
- Enriched lane: `Citations_search_citations_minimal` — AI-extracted records
- 7-8 preset fields (~400 chars/result) OR custom fields (~100 chars/result)
- Present top results to user for selection

**Stage 2: Analysis (Balanced Search)**
- OA lane: `Citations_search_oa_citations_balanced` — statutory basis, paragraph number
- Enriched lane: `Citations_search_citations_balanced` — passages, claim mapping
- 16-18 comprehensive fields (~2000 chars/result)

**Stage 3: Details (Citation Details — enriched only)**
- Use `Citations_get_citation_details` for specific citations
- Complete record with passage-location context
- Pass the enriched record's `id` field (there is no `citationIdentifier` field)

---

## workflows_pfw

## Citation + PFW Integration Workflows

### GETTING OFFICE ACTION TEXT FOR A CITATION

**⚠️ CRITICAL**: Both citation lanes return METADATA only, NOT actual documents.
Use the PFW MCP for the office action itself.

**Preferred path — direct OA tools (one call, no OCR):**

```python
# "What did the examiner say?" / "Why was this cited?"
oa = PFW_get_oa_text(app_number='17896175')   # latest_only=True for just the most recent

# "Which rejections did this reference carry?" — structured 102/103/112 indicators
rej = PFW_get_oa_rejections(app_number='17896175')
```

`PFW_get_oa_text` and `PFW_get_oa_rejections` serve office-action text directly
from the application number. **Do not route through
`PFW_get_application_documents` + OCR for office actions** — that is the old
document-bag round trip and it costs an extra call plus an OCR pass for the same
text.

Pair `PFW_get_oa_rejections` with the OA lane's `legalSectionCode` when you need
to confirm which statutory basis a specific cited reference supported.

**Fallback path — document bag (for documents the OA tools do not serve):**

```python
# Notices of Allowance, IDS forms, 892 forms, and any OA PFW_get_oa_text misses
docs = PFW_get_application_documents(
    app_number='17896175',
    document_code='NOA',    # See decoder below
    limit=20
)
content = PFW_get_document_content_with_ocr(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
```

**Document Code Decoder (Citation-Related Documents):**
- **CTNF**: Non-Final Office Action — prefer `PFW_get_oa_text`
- **CTFR**: Final Office Action Rejection — prefer `PFW_get_oa_text`
- **NOA**: Notice of Allowance (document bag only — OA tools do not serve NOAs)
- **892**: Examiner's Search Strategy & Citations List (the OA lane's source form)
- **IDS**: Applicant's Information Disclosure Statement (the 1449 source form)

**User Download (Provide PDF Link)**
```python
# When user says: "Get me the office action" or "I want to review it"
download = PFW_get_document_download(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
# Present as: **📁 [Download Office Action]({download['proxy_download_url']})**
```

### Examiner Citation Pattern Analysis

**⚠️ IMPORTANT**: Citation API does NOT contain examiner name fields.
Use PFW → Citations workflow for examiner analysis.

**Ultra-Minimal Mode Workflow (99% Token Reduction):**

```python
# STEP 1: PFW - Get examiner's applications (wildcard-first strategy)
last_name = 'SMITH'  # Extract from "SMITH, JANE"

pfw_apps = PFW_search_applications_minimal(
    query=f'examinerNameText:{last_name}* AND filingDate:[2015-01-01 TO *]',
    fields=[
        'applicationNumberText',
        'applicationMetaData.examinerNameText',
        'applicationMetaData.groupArtUnitNumber'
    ],  # ONLY 3 fields - 99% token reduction vs full data
    limit=50
)
# Result: ~5KB for 50 apps (vs ~25KB with preset minimal, ~500KB with full data)

# STEP 2: Analyze art unit distribution (wildcard returns multiple units)
from collections import Counter
art_unit_dist = Counter([
    app['applicationMetaData']['groupArtUnitNumber']
    for app in pfw_apps['applications']
])

# STEP 3: Get citations for top 20 applications only
# Lane choice: enriched for category mix + passage depth and any pre-2017 work;
# OA for the complete inventory and statutory basis (2017-10-01+ only).
citation_data = []
for app in pfw_apps['applications'][:20]:  # Limit to prevent token explosion
    citations = Citations_search_citations_minimal(
        criteria=f"patentApplicationNumber:{app['applicationNumberText']}",
        fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'citedDocumentIdentifier'],
        rows=50
    )
    citation_data.append({
        'app_number': app['applicationNumberText'],
        'citation_count': citations['response']['numFound'],
        'citations': citations['response']['docs']
    })

# STEP 3b (optional): statutory-basis profile — OA lane only
for app in pfw_apps['applications'][:20]:
    oa = Citations_search_oa_citations_minimal(
        application_number=app['applicationNumberText'],
        fields=['legalSectionCode', 'actionTypeCategory', 'parsedReferenceIdentifier'],
        rows=50
    )   # note: NO officeActionDate clause — that field does not exist in OA v2
```

**Why This Works:**
1. **Wildcard Strategy**: Higher hit rate than exact matches (handles name variations)
2. **Ultra-Minimal Fields**: Request only essential data (99% token reduction)
3. **Date Filtering**: 2015-01-01 filing date accounts for 2-year lag to office action
4. **Progressive Analysis**: Start with discovery, escalate only for key items

**Token Efficiency Summary:**
- PFW ultra-minimal: 50 apps × 3 fields = ~5KB
- Citations ultra-minimal: 1000 citations × 3 fields = ~60KB
- Total: ~65KB vs ~2.5MB without optimization = **97% savings**

### Alternative: Patent XML Retrieval (Use with Caution)

**⚠️ IMPORTANT**: Document retrieval (above) is the **primary workflow** for Citations MCP.
Office action documents (CTFR, NOA, 892) contain the citation context and examiner reasoning.

**If you need patent XML data (rare for citation workflows):**

```python
# Use PFW's XML tool with token optimization
xml_data = PFW_get_patent_or_application_xml(
    application_number='17896175',
    include_fields=['abstract', 'claims'],  # Select only needed fields
    include_raw_xml=False  # ⭐ CRITICAL: 91-99% token reduction!
)
# Without include_raw_xml=False: ~50KB of raw XML included
# With include_raw_xml=False: ~4.5KB (91% reduction)
```

**When to Use XML vs Document Retrieval:**

| Use Case | Recommended Tool | Reason |
|----------|------------------|--------|
| Citation context & examiner reasoning | **PFW_get_oa_text** (or **PFW_get_oa_rejections** for rejection types) | Direct office-action text — no document-bag + OCR round trip |
| Claim text for prior art comparison | **PFW_get_patent_or_application_xml** (include_fields=['claims'], include_raw_xml=False) | Structured claim data from patent XML |
| Patent abstract/description | **PFW_get_patent_or_application_xml** (include_fields=['abstract', 'description'], include_raw_xml=False) | Structured patent content |
| Examiner's citation decisions | **PFW_get_application_documents** (document_code='892') | 892 document lists examiner citations |

**Key Points:**
- Always use `include_raw_xml=False` (saves ~45KB per request, 91% reduction)
- For citations workflow, **document retrieval is preferred** over XML retrieval
- `include_fields=['citations']` has limited utility since Citations MCP already provides comprehensive citation metadata
- XML tool is best for patent content (claims, abstract), not citation context

---

## workflows_ptab

## Citation + PTAB Integration Workflows

### Prior Art Validation for PTAB Challenges

**Use Case**: Validate prior art cited in IPR/PGR proceedings against prosecution history.

**Workflow:**
```python
# STEP 1: PTAB - Get IPR proceedings for patent (ultra-minimal mode for 99% reduction)
# Note: PTAB API now has separate search tools for trials, appeals, and interferences
# - Trials: PTAB_search_trials_minimal/balanced/complete (IPR/PGR/CBM proceedings)
# - Appeals: PTAB_search_appeals_minimal/balanced/complete (Ex Parte/Interference Appeals)
# - Interferences: PTAB_search_interferences_minimal/balanced/complete (Derivations/Interferences)
# - Documents: PTAB_get_documents(identifier, identifier_type) for all proceeding types
#
# Token Optimization: All search tools support `fields` parameter for ultra-minimal queries:
# - Ultra-minimal (2-3 fields): 99% reduction - Use for identifier correlation
# - Preset minimal (10-15 fields): 68% reduction - Use for discovery/presentation
# - Preset balanced (30-50 fields): 13.5% reduction - Use for detailed analysis

ptab_proceedings = PTAB_search_trials_minimal(
    patent_number='9049188',
    fields=['trialNumber', 'trialMetaData.trialStatusCategory', 'patentOwnerData.patentNumber'],
    limit=20
)

# STEP 2: Citation - Get prosecution citations
# patent_number takes the granted number directly and crosswalks it to the
# application serial; publicationNumber holds pre-grant publications and would
# not match 9049188.
citations = Citations_search_citations_balanced(
    patent_number='9049188',
    rows=100
)

# STEP 3: Compare prior art
ptab_prior_art = set()  # Extract from PTAB proceedings
prosecution_citations = {c['citedDocumentIdentifier'] for c in citations['response']['docs']}

# Identify new prior art in PTAB (not cited during prosecution)
new_prior_art = ptab_prior_art - prosecution_citations
```

### PTAB Vulnerability Assessment

**Use Case**: Identify patents vulnerable to post-grant challenges based on citation patterns.

**Indicators of Vulnerability:**
- Low examiner citation count (minimal prior art search)
- No NPL citations (narrow search scope)
- Applicant-only citations (IDS) with no examiner review
- Art unit with low citation norms

**Workflow:**
```python
# Get citation patterns for portfolio patents
for patent in portfolio:
    citations = Citations_search_citations_minimal(
        patent_number=patent,   # granted number: crosswalked to the application
        fields=['examinerCitedReferenceIndicator', 'citationCategoryCode'],
        rows=100
    )

    # Calculate vulnerability score
    examiner_cites = sum(1 for c in citations if c['examinerCitedReferenceIndicator'] == 'true')
    npl_cites = sum(1 for c in citations if c['citationCategoryCode'] == 'NPL')

    if examiner_cites < 5 or npl_cites == 0:
        print(f"⚠️ High PTAB vulnerability: {patent}")
```

### Cross-Reference Fields

**PTAB → Citations:**
- `patentNumber` → `publicationNumber`
- Use for: Prosecution citation analysis for challenged patents

**Citations → PTAB:**
- `publicationNumber` → `patentNumber`
- Use for: PTAB challenge research for cited patents

---

## workflows_fpd

## Citation + FPD Integration Workflows

### Petition Red Flags in Prosecution Quality

**Use Case**: Correlate petition filing with citation patterns to identify prosecution quality issues.

**Workflow:**
```python
# STEP 1: FPD - Get petitions for application
petitions = FPD_Search_petitions_minimal(
    application_number='17896175',
    limit=10
)

# STEP 2: Citation - Get citation patterns
citations = Citations_search_citations_balanced(
    criteria=f'patentApplicationNumber:17896175 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# STEP 3: Analyze correlation
if petitions['response']['numFound'] > 0 and citations['response']['numFound'] < 5:
    print("⚠️ Petition filed with minimal prior art - possible examiner search quality issue")
```

### Art Unit Quality Assessment

**Use Case**: Use citation patterns to assess art unit prosecution quality.

**Indicators:**
- Citation density (citations per application)
- Examiner vs applicant citation ratio
- NPL citation usage
- Petition correlation with low citation counts

**Workflow:**
```python
# Get art unit citation statistics
citations = Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=200
)

# Get FPD petitions for same art unit
petitions = FPD_Search_petitions_minimal(
    art_unit='2854',
    decision_type='GRANTED',
    limit=100
)

# Calculate quality metrics
unique_apps = len(set(c['patentApplicationNumber'] for c in citations['response']['docs']))
citation_density = citations['response']['numFound'] / unique_apps
petition_rate = petitions['response']['numFound'] / unique_apps

if petition_rate > 0.2 and citation_density < 3:
    print(f"⚠️ Art unit 2854: High petition rate with low citation density")
```

### Cross-Reference Fields

**FPD → Citations:**
- `applicationNumber` → `patentApplicationNumber`
- Use for: Citation analysis for petitioned applications

**Citations → FPD:**
- `patentApplicationNumber` → `applicationNumber`
- Use for: Petition research for cited applications

---

## workflows_complete

## Complete Prosecution Lifecycle Analysis

### Four-MCP Integration: Citation + PFW + PTAB + FPD

**Use Case**: Comprehensive patent intelligence from filing through post-grant.

**Complete Workflow:**

```python
# PHASE 1: Citation Intelligence
citations = Citations_search_citations_balanced(
    patent_number='9049188',   # granted number: crosswalked to the application
    rows=100
)

examiner_citations = [c for c in citations['response']['docs']
                      if c['examinerCitedReferenceIndicator'] == 'true']

# PHASE 2: Prosecution History (PFW)
pfw_search = PFW_search_applications_minimal(
    query='patentNumber:9049188',
    fields=['applicationNumberText'],
    limit=1
)
app_number = pfw_search['applications'][0]['applicationNumberText']

# Get key prosecution documents
noa_docs = PFW_get_application_documents(
    app_number=app_number,
    document_code='NOA',
    limit=5
)

rejection_docs = PFW_get_application_documents(
    app_number=app_number,
    document_code='CTFR|CTNF',
    limit=10
)

# PHASE 3: Petition Analysis (FPD)
petitions = FPD_Search_petitions_minimal(
    application_number=app_number,
    limit=10
)

# PHASE 4: PTAB Challenges (ultra-minimal mode for 99% reduction)
ptab_proceedings = PTAB_search_trials_minimal(
    patent_number='9049188',
    fields=['trialNumber', 'patentOwnerData.patentNumber'],
    limit=10
)

# COMPREHENSIVE INTELLIGENCE REPORT
print(f"COMPLETE LIFECYCLE INTELLIGENCE")
print(f"================================")
print(f"Citation Intelligence:")
print(f"  - Total citations: {citations['response']['numFound']}")
print(f"  - Examiner citations: {len(examiner_citations)}")
print(f"")
print(f"Prosecution History:")
print(f"  - Application: {app_number}")
print(f"  - Allowances: {noa_docs['count']}")
print(f"  - Rejections: {rejection_docs['count']}")
print(f"")
print(f"Petition History:")
print(f"  - Total petitions: {petitions['response']['numFound']}")
print(f"")
print(f"PTAB Status:")
print(f"  - Proceedings: {ptab_proceedings.get('response', {}).get('numFound', 0)}")
```

### Strategic Intelligence Outputs

**1. Invalidity Analysis**
- Comprehensive prior art from prosecution citations
- PTAB prior art comparison
- Citation gap analysis

**2. Prosecution Quality**
- Citation thoroughness vs petition filing correlation
- Examiner search quality indicators
- Art unit citation norms

**3. PTAB Vulnerability**
- Citation patterns indicating search quality
- Prior art gaps exploitable in IPR
- Examiner citation selectivity

**4. Claim Construction**
- Examiner's interpretation from NOA documents
- Citation context for claim amendments
- Prosecution estoppel evidence

### Token Efficiency for Complete Workflow

**Without Optimization:**
- Citations: 100 results × 18 fields = ~200KB
- PFW: 50 docs × full metadata = ~500KB
- FPD: 10 petitions × full metadata = ~100KB
- PTAB: 10 proceedings × full metadata = ~200KB
- **Total: ~1MB**

**With Ultra-Minimal Optimization:**
- Citations: 100 results × 3 fields = ~30KB
- PFW: 50 docs × 2 fields = ~10KB
- FPD: 10 petitions × 3 fields = ~10KB
- PTAB: 10 proceedings × 3 fields = ~20KB
- **Total: ~70KB (93% reduction)**

---

## oa_citations

## OA Citations (v2) vs Enriched Citations (v3) — Run Both

### The default is TRY BOTH, not either/or

**Neither lane is a superset of the other, in either direction.** For any
completeness-sensitive question — litigation prior-art sweeps, art-unit or
examiner behavior studies, "was reference X ever cited" — the recommended
workflow is to query **both** `Citations_search_citations_*` and
`Citations_search_oa_citations_*`, then union and compare the results.

Take a single-lane shortcut only when the question needs a lane-exclusive
capability:

| Need | Lane | Why |
|---|---|---|
| Passage locations, claim mapping, quality score, NPL flag | **Enriched only** | `passageLocationText`, `relatedClaimNumberText`, `qualitySummaryText`, `nplIndicator` exist nowhere else |
| Statutory basis filter (102/103/112) | **OA only** | `legalSectionCode` + `actionTypeCategory` exist nowhere else |
| Date-windowed query | **Enriched only** | OA has no date field at all |
| Subject-patent lookup by parameter | **Both** | `patent_number` crosswalks a granted patent number to its application on either lane; enriched also takes an 11-digit publication number |
| Reverse lookup of a cited reference | **Both** | enriched `citedDocumentIdentifier`, OA `parsedReferenceIdentifier` — both via `criteria` |
| Everything else, especially "is this complete?" | **Both** | Union the results on `referenceKey` |

### The union key is `referenceKey`, not the raw identifier fields

**Both lanes carry a `referenceKey` on every row, at every tier. It is the only
correct key for unioning them.**

The two lanes write the same reference differently. Measured on application
12849948, 2026-09-04:

| Lane | Field | Value |
|---|---|---|
| OA (v2) | `parsedReferenceIdentifier` | `20060075466` |
| Enriched (v3) | `citedDocumentIdentifier` | `US 2006/0075466 A1` |
| Enriched (v3) | `publicationNumber` | `20060075466` |

Joining `parsedReferenceIdentifier` against `citedDocumentIdentifier` therefore
finds **zero** overlap on every application. The true answer on that
application is four references present in both lanes. The OA **minimal** tier
used to make it worse still: it carried no parsed identifier at all, only the
raw Form 892 string with the inventor name attached. It now carries
`parsedReferenceIdentifier` as well.

`referenceKey` normalises all of those forms to one value: uppercase, a leading
`US` dropped, spaces, slashes, hyphens, commas and periods dropped, the kind
code (`A1`, `B2`, `E`, `S`) dropped, series markers such as `RE` kept. It is
derived from `publicationNumber` then `citedDocumentIdentifier` on the enriched
lane, and from `parsedReferenceIdentifier` then `referenceIdentifier` on the OA
lane, and it is computed before the tier's field filter runs, so an
ultra-minimal custom `fields` list still gets the best available key.

**`referenceKey` is `null` when the row's identifier does not reduce to a
document number** (non-patent literature, free text, a blank identifier). On
the enriched lane the response envelope also carries
`rows_without_reference_identifier`, always present and `0` included. An
**absent** `citedDocumentIdentifier` key, a **null** one and an **empty
string** are ONE state, not three: a row can carry an empty
`publicationNumber` with the `citedDocumentIdentifier` key missing from the
JSON entirely. Measured blank-identifier rows: 2 of 5 on app 11752072, 4 of 8
on 12849948, 4 of 26 on 18407147. Those rows are real citations. Report them as
unresolved; never drop them, and never let them vanish from a union.

### Measured coverage (Tech Center 2100, measured 2026-08)

| Query | OA (v2) | Enriched (v3) |
|---|---|---|
| `techCenter:2100` (all) | **4,870,078** | 4,317,926 |
| `techCenter:2100` examiner-cited only | **3,711,459** | 3,619,296 |
| Art unit 2854 | **42,509** | 37,937 |
| App 18407147 (2024 filing) | **38** | 26 |
| App 12849948 (2012 office action) | 4 | **8** |
| Cited-patent reverse lookup, US 9,280,610 | **25** | 17 |

**Read these numbers carefully:**

1. **OA is usually broader, but not always, and never by a huge margin.** At
   tech-center scale the gap is ~13%; on examiner-cited references alone it
   narrows to ~2.5%. The enriched index is *not* a thin sample of the examiner
   record — it captures the large majority of it.
2. **Most of OA's surplus is applicant IDS citations, but neither lane holds
   the full 1449.** OA carries ~1.16M applicant-only (Form 1449) records in
   TC2100 vs ~0.70M in enriched, so if the question is "what did the applicant
   disclose", lean OA and still check enriched. **What you must not do is
   report either count as the applicant's complete IDS.** Measured against the
   patents' own References Cited pages, the union of BOTH lanes returns: US
   7,971,071 5 of 91; US 9,496,922 1 of 251; US 9,135,462 0 of about 620 (both
   lanes numFound 0); US 11,656,067, prosecuted 2021-2023 inside the documented
   window, 3 of 15, all three the examiner's own double-patenting family
   citations and none of the twelve references a later IPR petition relied on;
   US 12,539,322 (2025 prosecution) omitted an applicant-cited reference. On
   IDS-heavy files these lanes return close to what the examiner applied and
   little else, in every era. A reference's absence is NO evidence the
   applicant did not disclose it. For a complete 1449 record, read the IDS
   documents themselves through the PFW MCP.
3. **The direction can reverse on a specific application.** App 12849948
   returns 8 enriched records and only 4 OA records. Per-application, you
   cannot predict which lane wins. This is the single strongest argument for
   querying both.

### Coverage window: documented vs observed

**USPTO's published documentation gives BOTH APIs the same window** — office
actions mailed **2017-10-01 through ~30 days prior to the current date**.
Treat that as the official answer when describing the data to a user.

**In practice, both lanes have been observed serving records outside that
window.** This is a measured observation, not a documented guarantee, and it
matches practitioner experience that coverage often reaches back further than
the docs promise:

- **Enriched:** 1,905,220 of 4,317,926 TC2100 records (44.1%) carry an
  `officeActionDate` before 2017-10-01, back to roughly 2008.
- **OA:** cannot be date-filtered, but demonstrably contains such records too —
  see the verification below.

**Verification method (reproducible).** `officeActionDate` was cross-checked
against PFW, which holds the authoritative prosecution record:

| App | Enriched `officeActionDate` | PFW document date (authoritative) | Match |
|---|---|---|---|
| 12849948 | 2012-06-07 (CTNF) | CTNF `officialDate` 2012-06-07 | ✅ exact |
| 11802002 | 2010-02-01 (CTNF) | CTNF `officialDate` 2010-02-01 | ✅ exact |

So `officeActionDate` is the genuine office-action **mail date**, not the cited
reference's publication date (the cited documents in those records are from
2006 and 2005 respectively — different values).

For the OA lane, app 12849948's Form **892** — the source document OA v2 is
built from — carries PFW `officialDate` **2012-06-07**, and the OA lane returns
4 records for that application. Pre-2017 material is present there as well.

**How to state this to a user:** cite the documented 2017-10-01 window as the
official coverage, and add that coverage has in practice been observed beyond
it, so older prosecution is worth querying rather than assumed absent. Never
report an empty result on an older application as proof that no art was cited
without having tried both lanes.

### Practical both-lanes pattern

```python
# Completeness-sensitive question -> union both lanes.
enriched = Citations_search_citations_minimal(
    criteria='patentApplicationNumber:12849948', rows=100
)
oa = Citations_search_oa_citations_minimal(
    application_number='12849948', rows=100
)   # note: NO date clause, NO publicationNumber — both 400 on this lane

# Compare numFound from each, then union on referenceKey. The server computes
# it on both lanes precisely so this join works:
enriched_keys = {d["referenceKey"] for d in enriched["response"]["docs"]
                 if d.get("referenceKey")}
oa_keys = {d["referenceKey"] for d in oa["response"]["docs"]
           if d.get("referenceKey")}
union = enriched_keys | oa_keys
both  = enriched_keys & oa_keys

# Rows the union cannot carry, because they have no joinable identifier:
unresolved = enriched["rows_without_reference_identifier"]

# Report both totals, the union, the overlap, AND the unresolved count; say
# which lane contributed what. Never join on the raw identifier fields, and
# never report the union without the unresolved rows beside it.
```

### Field vocabulary does not transfer — hard failures

The two indexes reject each other's field names with HTTP 400. These are the
mistakes that actually happen:

```python
# ❌ ERRORS — officeActionDate does not exist in OA v2
Citations_search_oa_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]'
)
# "Invalid criteria: Invalid field name: officeActionDate."
# ✅ OA has NO office-action date field. Drop the clause entirely.
Citations_search_oa_citations_minimal(art_unit='2854')

# ❌ ERRORS — publicationNumber does not exist in OA v2
#    This server's 400 here is DELIBERATE and worth knowing about: the raw
#    upstream API does NOT reject the clause, it answers HTTP 200 with
#    numFound 0, which reads as "this patent was never cited" and is silently
#    wrong. A refusal you can see beats a zero you cannot.
Citations_search_oa_citations_minimal(criteria='publicationNumber:9049188')
# ✅ The patent_number PARAMETER crosswalks to the application serial for you
#    (the field still does not exist, so it can never go in `criteria`):
Citations_search_oa_citations_minimal(patent_number='9049188')
#    To find where a patent was CITED, use parsedReferenceIdentifier:
Citations_search_oa_citations_minimal(criteria='parsedReferenceIdentifier:9280610')

# ❌ ERRORS — legalSectionCode does not exist in enriched v3
Citations_search_citations_minimal(criteria='techCenter:2100 AND legalSectionCode:103')
# ✅ Statutory basis is an OA-only capability.
Citations_search_oa_citations_minimal(criteria='techCenter:2100 AND legalSectionCode:103')
```

**`createDateTime` in OA is an ETL load timestamp, not the office action date.**
Sampled OA records carry 2025 load stamps regardless of when the office action
issued. Never present it as prosecution chronology and never range-filter on it
expecting office-action semantics.

**Matching a cited reference in OA:** use `parsedReferenceIdentifier` (normalized,
e.g. `9280610`), not `referenceIdentifier` — the raw string format varies across
records for the same patent (`US 9280610 B2` vs `US 9,280,610 B2`).

### Neither index has examiner names

There is **no examiner name field in either lane** — `examinerNameText` returns
HTTP 400 on the enriched API. Examiner-level analysis must go through PFW
(`PFW_search_applications_minimal` on `examinerNameText`) to get that examiner's
application numbers, then query citations by application. See `workflows_pfw`.

---

## citation_codes

## Citation Category Codes (X/Y/A)

### Category Definitions

⚠️ X, Y, A are **relevance ratings** — both US and foreign patents can carry any code.
The old descriptions "X = US patents, Y = foreign patents" are incorrect.

**X - Anticipatory (§102/103 basis)**
- Highly relevant reference — anticipates the claim alone (§102) or obvious alone (§103)
- Most strategically important citations; strongest PTAB/litigation risk indicator
- Can be any patent document (US or foreign) or NPL

**Y - Combinable (§103 basis)**
- Combined with other X or Y citations to establish obviousness (§103)
- Often cited in groups; indicates examiner's obviousness theory
- Can be any patent document (US or foreign) or NPL

**A - Background Art**
- Supplementary / background reference
- Less critical to the rejection; not used for §102 or §103 alone
- Cited for context, technology understanding, or claim interpretation

**Non-Patent Literature (NPL)**
⚠️ NPL is NOT a citationCategoryCode value — `citationCategoryCode:NPL` returns 0 results.
NPL references are identified by: `nplIndicator:true` (boolean field).
NPL documents can carry X, Y, or A category codes like any other reference.
- Technical papers, articles, standards documents
- Indicates bleeding-edge technology or academic art
- Critical for software, biotech, chemical arts

### Strategic Analysis

**High X Citation Rate (>70%)**
- Strong domestic prior art foundation
- Indicates mature technology area
- Lower PTAB vulnerability (thorough search)

**High Y Citation Rate (>30%)**
- International technology competition
- Consider foreign filing strategy
- May indicate PCT origins

**NPL Citations Present** (`nplIndicator:true`)
- Examiner performed thorough search beyond patent databases
- Technology at research frontier
- Academic prior art considerations

**Low Total Citations (<5)**
- ⚠️ Possible search quality issue
- Higher PTAB vulnerability
- Consider FPD petition correlation

### Examiner vs Applicant Citations

**High Examiner Citation Rate (>80%)**
- Examiner actively searching
- Strong prosecution quality
- Lower petition risk

**High Applicant Citation Rate (>50%)**
- Applicant disclosed extensive prior art (IDS)
- May indicate defensive disclosure
- Check for duty of disclosure compliance

### Query Examples

```python
# Get only X citations (US patents)
Citations_search_citations_minimal(
    criteria='citationCategoryCode:X AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# Get NPL citations (bleeding-edge tech) — use nplIndicator, NOT citationCategoryCode:NPL
Citations_search_citations_minimal(
    criteria='nplIndicator:true AND techCenter:2100',
    rows=50
)

# Get examiner citations only
Citations_search_citations_minimal(
    criteria='examinerCitedReferenceIndicator:true AND officeActionDate:[2023-01-01 TO *]',
    rows=100
)
```

---

## data_coverage

## Data Coverage

### Documented window (both lanes)

USPTO's published documentation gives **both** APIs the same coverage: office
actions mailed **2017-10-01 through ~30 days prior to the current date**.

| | OA Citations (v2) | Enriched Citations (v3) |
|---|---|---|
| Documented window | 2017-10-01 → T-30d | 2017-10-01 → T-30d |
| Date field | **none** | `officeActionDate` |
| Date filtering possible? | No | Yes |

### Observed coverage exceeds the documented window

Measured on this API, **both lanes return records older than the documented
floor**. State the documented window as the official answer, and treat older
material as "worth querying" rather than guaranteed:

- **Enriched, TC2100 bands:**

  | Band | Records | Share |
  |---|---|---|
  | Before 2008-01-01 | 2,238 | 0.05% |
  | Before 2010-01-01 | 199,180 | 4.6% |
  | Before 2017-10-01 | 1,905,220 | **44.1%** |
  | All | 4,317,926 | 100% |

- **OA:** no date field, so it cannot be banded — but app 12849948's Form 892
  (the OA v2 source document) is dated 2012-06-07 in PFW and the OA lane
  returns 4 records for that application.

**`officeActionDate` verified as the true OA mail date** against PFW's
authoritative document dates: app 12849948 → 2012-06-07 CTNF (exact match); app
11802002 → 2010-02-01 CTNF (exact match). It is not the cited reference's
publication date — those cited documents are from 2006 and 2005.

### Date Handling Strategies

**Enriched lane — date filtering works:**

```python
# ✅ Pre-2017 windows return results in practice
Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2010-01-01 TO 2016-12-31]',
    rows=100
)
```

Add an `officeActionDate:[2017-10-01 TO *]` clause only when you deliberately
want the documented window (e.g. reporting strictly-documented coverage). Do not
add it reflexively — it discards ~44% of the records the index actually serves.

**OA lane — no date filtering exists:**

```python
# ❌ ERRORS with HTTP 400 - officeActionDate is not an OA field
Citations_search_oa_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]'
)

# ✅ Just omit the date clause
Citations_search_oa_citations_minimal(art_unit='2854')
```

If you need a date-scoped subset of raw citations, there is no way to get it
from OA directly. Get the date-scoped application list from the enriched lane
(or PFW), then query OA per application number.

### Eligibility Quick Check

| Scenario | First OA Date | Documented? | Observed in practice |
|----------|---------------|-------------|----------------------|
| Recent app | 2022-01-01 | ✅ Both lanes | ✅ Both |
| Mid app | 2017-06-01 | ❌ Outside window | ✅ Seen in both |
| Older app | 2012-06-01 | ❌ Outside window | ✅ Verified in both (app 12849948) |
| Very old app | 2006-01-01 | ❌ Outside window | ⚠️ Rare (enriched thins out below ~2008) |

**Zero results is not proof of "no citations"** — and it is not proof of the
coverage floor either. Try the other lane before concluding anything.

### Cross-MCP Date Coordination

**PFW + Citations Integration:**
```python
# Scope the PFW filing-date filter to the era you actually want to report on.
# 2015-01-01 caps an examiner study at ~10 recent years; go earlier if the
# question is career-spanning — older office actions do appear in practice.
pfw_apps = PFW_search_applications_minimal(
    query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
    fields=['applicationNumberText'],
    limit=50
)

# Enriched lane: add an officeActionDate clause only if you want that window.
for app in pfw_apps:
    citations = Citations_search_citations_minimal(
        criteria=f'patentApplicationNumber:{app}',
        rows=50
    )

# OA lane: no date clause is possible — query by application number.
for app in pfw_apps:
    oa = Citations_search_oa_citations_minimal(application_number=app, rows=50)
```

---

## fields

## Field Selection Strategies

### Predefined Field Sets

**⚠️ The two lanes have different field vocabularies.** Confirm with
`Citations_get_available_fields` (enriched, 22 fields) or
`Citations_get_oa_citation_fields` (OA, 16 fields) before writing criteria —
a wrong field name is an HTTP 400, not an empty result.

**citations_minimal (enriched, 8 fields):**
- `id` (the record identifier — pass this to `Citations_get_citation_details`)
- `patentApplicationNumber`
- `publicationNumber`
- `groupArtUnitNumber`
- `citationCategoryCode`
- `techCenter`
- `officeActionDate`
- `examinerCitedReferenceIndicator`

**citations_balanced (enriched, 18 fields):**
All minimal fields plus:
- `citedDocumentIdentifier`
- `passageLocationText` (column/line/figure/paragraph/claim locators)
- `relatedClaimNumberText`
- `qualitySummaryText`
- `officeActionCategory`
- `nplIndicator`
- `countryCode`, `kindCode`, `inventorNameText`, `createDateTime`,
  `workGroupNumber`, `applicantCitedExaminerReferenceIndicator`,
  `createUserIdentifier`, `obsoleteDocumentIdentifier`

**OA citations (v2, all 16 fields):**
`patentApplicationNumber`, `groupArtUnitNumber`, `techCenter`, `workGroup`,
`referenceIdentifier`, `parsedReferenceIdentifier`, `actionTypeCategory`,
`legalSectionCode`, `paragraphNumber`, `examinerCitedReferenceIndicator`,
`applicantCitedExaminerReferenceIndicator`,
`officeActionCitationReferenceIndicator`, `createDateTime`,
`createUserIdentifier`, `obsoleteDocumentIdentifier`, `id`

### Fields That Do NOT Exist (common HTTP 400 causes)

| Field used | Reality |
|---|---|
| `examinerNameText` | **In neither lane.** Go through PFW for examiner analysis. |
| `firstApplicantName` / `firstApplicantNameText` | Not an enriched field. The `applicant_name` convenience param builds this query and **silently returns 0 results** — do not rely on it. |
| `citingPassageText` | Enriched field is `passageLocationText`. |
| `citationIdentifier` | Enriched field is `id`. |
| `officeActionDate` on the OA lane | OA has no date field at all. |
| `publicationNumber` on the OA lane | Not an OA field. Use the `patent_number` parameter, which crosswalks to `patentApplicationNumber`. |
| `legalSectionCode` on the enriched lane | Statutory basis is OA-only. |
| `citationCategoryCode:NPL` | Returns 0 — use `nplIndicator:true`. |

### Ultra-Minimal Mode (Custom Fields)

**99% Token Reduction Examples:**

```python
# For PFW integration (2 fields only)
Citations_search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier', 'patentApplicationNumber'],
    rows=100
)
# Token cost: ~10KB (vs ~400KB with preset minimal)

# For frequency analysis (1 field only!)
Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier'],
    rows=500
)
# Token cost: ~25KB (vs ~2MB with preset minimal)

# For examiner behavior (3 fields)
Citations_search_citations_minimal(
    criteria='officeActionDate:[2023-01-01 TO *]',
    fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=200
)
# Token cost: ~20KB (vs ~800KB with preset minimal)
```

### Solr/Lucene Query Syntax

**Field Searches:**
```
patentApplicationNumber:18180061        # Exact match
groupArtUnitNumber:2854                 # Art unit
techCenter:2100                         # Technology center
citedDocumentIdentifier:US*             # Wildcard
publicationNumber:20060075466           # 11-digit PRE-GRANT publication number
                                        # (for a granted patent number, use the
                                        #  patent_number parameter, not criteria)
```

**Boolean Operators:**
```
citationCategoryCode:X AND techCenter:2100              # AND
citationCategoryCode:X OR citationCategoryCode:Y        # OR
techCenter:2100 NOT groupArtUnitNumber:1600             # NOT
(citationCategoryCode:X OR citationCategoryCode:Y) AND techCenter:2100  # Grouping
```

**Wildcards:**
```
citedDocumentIdentifier:US*             # Prefix wildcard
patentApplicationNumber:18*             # Application wildcard
```

**Ranges:**
```
groupArtUnitNumber:[2000 TO 2999]                      # Numeric range
officeActionDate:[2023-01-01 TO 2023-12-31]            # Date range
officeActionDate:[2017-10-01 TO *]                     # Open-ended range
```

**Date Formats:**
```
officeActionDate:[2023-01-01 TO 2023-12-31]            # Standard format
officeActionDate:[20230101 TO 20231231]                # Compact format
createDateTime:[2024-01-01T00:00:00Z TO *]             # Timestamp format
```

**Special Indicators:**
```
examinerCitedReferenceIndicator:true                   # Boolean field
nplIndicator:true                                      # NPL only (use this — NOT citationCategoryCode:NPL)
```

### Common Query Patterns

**Examiner Citation Analysis:**
```python
Citations_search_citations_minimal(
    criteria='examinerCitedReferenceIndicator:true AND groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)
```

**Technology Landscape:**
```python
Citations_search_citations_minimal(
    criteria='techCenter:2100 AND citationCategoryCode:X AND officeActionDate:[2023-01-01 TO *]',
    rows=100
)
```

**NPL Analysis:**
```python
# ⚠️ citationCategoryCode:NPL returns 0 results — use nplIndicator:true instead
Citations_search_citations_minimal(
    criteria='nplIndicator:true AND techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=50
)
```

---

## errors

## Common Errors and Troubleshooting

### Wrong-Lane Field Errors (most common failure)

**Error**: `Invalid criteria: Invalid field name: officeActionDate` (HTTP 400)

**Cause**: An enriched-lane field name was sent to the OA lane. OA v2 has **no
office-action date field**; `officeActionDate`, `publicationNumber`,
`citationCategoryCode` and `nplIndicator` all 400 there.

**Solution**: Drop the clause — OA cannot be date-filtered at all.

```python
# ❌ WRONG — 400
Citations_search_oa_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]'
)

# ✅ CORRECT
Citations_search_oa_citations_minimal(art_unit='2854')
```

**Error**: `Invalid field name: legalSectionCode` on the enriched lane

**Cause**: Statutory basis is OA-only. Move the query to
`Citations_search_oa_citations_minimal`. The 400 message now names the lane
that holds the field, in both directions.

**Error**: `Invalid field name: legalSectionCode` from
`Citations_get_citation_statistics`

**Cause**: that tool aggregates the **enriched lane only**. It validates
`criteria` against the enriched whitelist, it has no `lane` parameter, and the
OA index has no statistics path on this server. This is a documented limit, not
a clause to rephrase.

**Solution**: count the OA lane yourself with the OA search tools and read
`response.numFound`, which is the whole-result total, not the page size. One
call per bucket reproduces the same breakdown shape:

```python
# ❌ WRONG: 400, and no rephrasing of the clause will help
Citations_get_citation_statistics(criteria='techCenter:2100 AND legalSectionCode:103')

# ✅ CORRECT: one cheap call per bucket, rows=1
for section in ('102', '103', '112'):
    r = Citations_search_oa_citations_minimal(
        criteria=f'techCenter:2100 AND legalSectionCode:{section}', rows=1
    )
    print(section, r['response']['numFound'])
```

Always say which lane each number came from. The two indexes are independent
and neither is a superset of the other, so an enriched statistic and an OA
count are not interchangeable.

### Patent Numbers: the Crosswalk, and What Each Lane Actually Holds

**Neither citation index stores a granted patent number.** The enriched lane's
`publicationNumber` holds 11-digit PRE-GRANT publication numbers; the OA lane has
no patent-number field at all (`publicationNumber` returns 400 there). Both
indexes key on `patentApplicationNumber`.

**All four search tools therefore take `patent_number` and resolve it for you**
(added 2026-09-02). A 7-8 digit granted patent number is crosswalked to its
application serial with one USPTO ODP applications-search call and queried as
`patentApplicationNumber`; on the enriched lane an 11-digit value is queried
directly as `publicationNumber`. Commas, spaces and a `US` prefix are accepted,
so `7971071`, `7,971,071` and `US 7,971,071` are the same input. A kind-code
suffix is NOT accepted: `US9049188B2` is refused with a 400 naming the accepted
forms. `application_number` is a separate parameter and is digits only, so a
slashed or comma-separated serial such as `14/171,705` is not a valid value
there and builds a query that matches nothing rather than raising.

Every response says how the input was read:

```json
"patent_number_resolution": {
  "input": "7,971,071",
  "interpreted_as": "granted_patent",
  "resolved_application_number": "11752072",
  "queried_field": "patentApplicationNumber",
  "source": "USPTO ODP applications search"
}
```

`interpreted_as` is `"publication"` (enriched lane only) for an 11-digit value,
and there is no `resolved_application_number` because nothing was crosswalked.

**Failures are 400s, not zero-results.** A number that resolves to no
application, a value that is neither 7-8 nor 11 digits, an 11-digit publication
number on the OA lane, and a `patent_number` that disagrees with a
`application_number` passed alongside it are all refused with a message naming
the three accepted forms: granted patent number, 11-digit publication number,
application serial.

**`application_number` is unchanged** — it is the application serial, and it
still collides in shape with 8-digit patent numbers, so pass a patent number as
`patent_number` and let the crosswalk decide. The PFW MCP remains the tool for
the reverse direction:

```python
# application serial -> patent number
PFW_search_applications_minimal(query='applicationNumberText:12849948')
```

### Date Range Errors

**Error**: Thin or empty results on an older office action

**Cause**: Usually an over-restrictive date clause, or having queried only one
lane. The documented floor is 2017-10-01, but both lanes serve older records in
practice — an empty result is not proof of the floor.

**Solution**: Drop the date clause and try the other lane.

```python
# ❌ Over-restrictive — discards ~44% of the records enriched actually serves
Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]'
)

# ✅ Enriched returns pre-2017 windows in practice
Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2010-01-01 TO 2016-12-31]'
)

# ✅ And always cross-check the other lane before concluding
Citations_search_oa_citations_minimal(art_unit='2854')
```

### Field Name Errors

**Error**: "Field not found" or 400 Bad Request

**Cause**: Invalid field names in query or fields parameter — or the right field
name sent to the wrong lane.

**Solution**: Use the field-discovery tool **for the lane you are querying**

```python
fields_info = Citations_get_available_fields()      # enriched v3 (22 fields)
oa_fields   = Citations_get_oa_citation_fields()    # OA v2 (16 fields)
```

### Silent Zero Results

**Error**: `numFound: 0` with no error raised

**Cause**: `applicant_name` builds a `firstApplicantName:` query against a field
that does not exist on the enriched API — it returns zero rather than 400.

**Solution**: Do not filter by applicant on this MCP. Resolve the applicant's
applications through PFW, then query citations by application number.

### Query Syntax Errors

**Error**: "Invalid query syntax" or parsing errors

**Cause**: Malformed Solr/Lucene query syntax

**Solution**: Use `Citations_validate_query()` before execution

```python
# Validate complex query
validation = Citations_validate_query(
    query='citationCategoryCode:X AND techCenter:2100 NOT groupArtUnitNumber:1600'
)

if validation['valid']:
    # Proceed with search
    Citations_search_citations_minimal(criteria=query, rows=100)
```

### Cross-MCP Integration Errors

**Error**: "Application number not found" when integrating with PFW

**Cause**: Application filed before 2015 or office action before 2017-10-01

**Solution**: Check filing date and office action date eligibility

```python
# STEP 1: Check PFW filing date
pfw_app = PFW_search_applications_minimal(
    application_number='12345678',
    fields=['applicationNumberText', 'applicationMetaData.filingDate']
)

filing_date = pfw_app['applications'][0]['applicationMetaData']['filingDate']

# STEP 2: Only search citations if filing date >= 2015-01-01
if filing_date >= '2015-01-01':
    citations = Citations_search_citations_minimal(
        application_number='12345678',
        date_start='2017-10-01'
    )
else:
    print(f"⚠️ Application filed {filing_date} - before citation data coverage")
```

### Empty Results

**Common Causes:**
1. Date range outside 2017-10-01 to present
2. Application number has no office actions in date range
3. Incorrect field values (e.g., wrong art unit number)
4. Query syntax error (silent failure)

**Debugging Steps:**
1. Validate query syntax with `Citations_validate_query()`
2. Check date range is within 2017-10-01 to present
3. Broaden search criteria to verify data exists
4. Check field names with `Citations_get_available_fields()`

---

## cost

## Cost Optimization Strategies

### Token Efficiency Hierarchy

**Level 1: Ultra-Minimal Mode (99% reduction)**
```python
# 1-2 fields for frequency/discovery
Citations_search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier'],  # Only 1 field!
    rows=500
)
# Token cost: ~25KB (vs ~2MB with preset minimal)
```

**Level 2: Preset Minimal (90-95% reduction)**
```python
# 8 preset fields for discovery
Citations_search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)
# Token cost: ~40KB
```

**Level 3: Custom Minimal (75-90% reduction)**
```python
# 3-5 custom fields for targeted analysis
Citations_search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=100
)
# Token cost: ~15KB
```

**Level 4: Balanced (70-80% reduction)**
```python
# 18 preset fields for comprehensive analysis
Citations_search_citations_balanced(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=50
)
# Token cost: ~100KB
```

### Progressive Disclosure

**Stage 1: Discovery (Minimal)**
- Use ultra-minimal mode (1-3 fields)
- High volume (100-500 results)
- Identify patterns and candidates
- Cost: ~10-50KB

**Stage 2: Analysis (Custom Minimal)**
- Use custom fields (3-5 fields)
- Medium volume (20-50 results)
- Detailed analysis of candidates
- Cost: ~10-25KB

**Stage 3: Details (Balanced or Details)**
- Use balanced or Citations_get_citation_details
- Low volume (5-10 results)
- Complete analysis of final selections
- Cost: ~20-50KB

**Total Cost: ~40-125KB vs 500KB-2MB without optimization**

### Cross-MCP Optimization

**PFW + Citations Integration:**
```python
# Ultra-efficient workflow
# STEP 1: PFW discovery (1 field only)
pfw_apps = PFW_search_applications_minimal(
    query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
    fields=['applicationNumberText'],  # Only app numbers!
    limit=50
)
# Cost: ~2-3KB

# STEP 2: Citation analysis (3 fields, top 20 only)
for app in pfw_apps['applications'][:20]:
    citations = Citations_search_citations_minimal(
        criteria=f'patentApplicationNumber:{app["applicationNumberText"]} AND officeActionDate:[2017-10-01 TO *]',
        fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'citedDocumentIdentifier'],
        rows=50
    )
# Cost: ~30-40KB

# Total: ~35-45KB vs ~500KB+ without optimization (92% savings)
```

### Result Limiting

**Best Practices:**
- Discovery: 50-100 results
- Analysis: 20-50 results
- Details: 5-10 results
- Cross-MCP: Limit to top 20 applications (prevents token explosion)

### Query Optimization

**Efficient Query Patterns:**
```python
# ✅ GOOD: Specific field searches with date constraint
'groupArtUnitNumber:2854 AND officeActionDate:[2023-01-01 TO *]'

# ✅ GOOD: Limited date ranges
'officeActionDate:[2023-01-01 TO 2023-12-31]'

# ⚠️ OKAY: Broader searches with field limits
Citations_search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citationCategoryCode', 'groupArtUnitNumber'],
    rows=200
)

# ❌ AVOID: Open-ended searches without field limits
Citations_search_citations_balanced(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=500
)  # Expensive!
```

### Summary

**Token Reduction Potential:**
- Ultra-minimal mode: **99% reduction** (1-2 fields)
- Custom minimal mode: **75-90% reduction** (3-5 fields)
- Preset minimal: **90-95% reduction** (8 fields)
- Balanced: **70-80% reduction** (18 fields)

**Cost Optimization Formula:**
1. Start with ultra-minimal discovery (1-3 fields)
2. Filter results to top candidates
3. Escalate to custom minimal for analysis (3-5 fields)
4. Use balanced/details only for final selections
5. Limit cross-MCP integration to top 20 items
