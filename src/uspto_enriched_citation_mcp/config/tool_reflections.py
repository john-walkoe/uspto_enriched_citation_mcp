"""
Tool reflections and LLM guidance for USPTO Enriched Citation MCP.

This module provides sectioned guidance for context-efficient access.
Each section is 1-12KB instead of 62KB for all content.
"""


def _get_overview_section() -> str:
    """Overview section with available sections and quick reference"""
    return """## Available Sections and Quick Reference

### 🎯 Quick Reference Chart - What section for your question?

- 🔍 **"Find citations by examiner/application/tech"** → `fields`
- 📄 **"Understand citation categories (X/Y/NPL)"** → `citation_codes`
- 🔖 **"Citation data coverage (2017+)"** → `data_coverage`
- 🤝 **"PFW workflow for office action documents"** → `workflows_pfw`
- 🚩 **"PTAB citation correlation"** → `workflows_ptab`
- 📊 **"FPD petition citation patterns"** → `workflows_fpd`
- 🏢 **"Complete lifecycle analysis"** → `workflows_complete`
- ⚙️ **"Tool guidance and parameters"** → `tools`
- ❌ **"Search errors or query issues"** → `errors`
- 💰 **"Reduce API costs and optimize"** → `cost`

### Available Sections:
- **overview**: Available sections and tool summary (this section)
- **workflows_pfw**: Citation + PFW integration workflows
- **workflows_ptab**: Citation + PTAB integration workflows
- **workflows_fpd**: Citation + FPD integration workflows
- **workflows_complete**: Four-MCP complete lifecycle analysis
- **citation_codes**: X/Y/A/NPL category decoder and strategic guidance
- **data_coverage**: 2017+ eligibility and date handling
- **fields**: Field selection strategies and Solr/Lucene syntax
- **tools**: Tool-specific guidance and parameters
- **errors**: Common error patterns and troubleshooting
- **cost**: Cost optimization strategies

### Context Efficiency Benefits:
- **90-95% token reduction** (1-12KB per section vs 62KB total)
- **Targeted guidance** for specific workflows
- **Same comprehensive content** organized for efficiency
- **Consistent experience** across all USPTO MCPs"""


def _get_tools_section() -> str:
    """Tools section with tool-specific guidance"""
    return """## Core Tools Overview

### Search Tools (Progressive Disclosure)

**search_citations_minimal** - Citation Discovery
- **Purpose**: Fast citation discovery with essential fields (90-95% context reduction)
- **Use Cases**: Initial research, volume citation analysis, pattern identification
- **Fields**: Core identifiers, citation categories, art units, temporal data (8 fields)
- **Ultra-Minimal Mode**: Custom fields parameter for 99% reduction (2-3 fields only)
- **Recommended**: 50-100 results for discovery workflow
- **Date Range**: officeActionDate from 2017-10-01 to 30 days ago (API availability)

**search_citations_balanced** - Detailed Citation Analysis
- **Purpose**: Comprehensive citation analysis with full context (70-80% context reduction)
- **Use Cases**: Detailed analysis, cross-MCP integration, legal research
- **Fields**: All citation metadata, classifications, cross-reference data (18 fields)
- **Ultra-Minimal Mode**: Custom fields parameter for 99% reduction (2-3 fields only)
- **Recommended**: 20-50 results for analysis workflow
- **Date Range**: officeActionDate from 2017-10-01 to 30 days ago (API availability)

### Detail Tools

**get_citation_details** - Full Citation Record
- **Purpose**: Complete citation details with optional citing context
- **Use Cases**: Specific citation analysis, passage examination, full record retrieval
- **Features**: Citation passage analysis, decision context, outcome verification
- **⚠️ IMPORTANT**: Returns citation METADATA only, NOT actual documents

**get_available_fields** - Field Discovery
- **Purpose**: Discover searchable field names and query syntax
- **Use Cases**: Query construction, field validation, syntax learning

**validate_query** - Query Optimization
- **Purpose**: Validate Solr/Lucene syntax and get optimization suggestions
- **Use Cases**: Query debugging, performance optimization, syntax learning

**get_citation_statistics** - Statistical Analysis
- **Purpose**: Get database statistics and aggregations
- **Use Cases**: Volume analysis, trend identification, strategic planning

### Progressive Disclosure Strategy

**Stage 1: Discovery (Minimal Search)**
- Use `search_citations_minimal` for broad exploration
- 8 preset fields (~400 chars/result) OR custom fields (~100 chars/result)
- Present top results to user for selection

**Stage 2: Analysis (Balanced Search)**
- Use `search_citations_balanced` for selected citations
- 18 comprehensive fields (~2000 chars/result)
- Detailed analysis for critical citations

**Stage 3: Details (Citation Details)**
- Use `get_citation_details` for specific citations
- Complete record with citing passage context
- Full metadata for legal analysis"""


def _get_workflows_pfw_section() -> str:
    """PFW + Citation integration workflows"""
    return """## Citation + PFW Integration Workflows

### 2-STEP PFW MCP WORKFLOW FOR DOCUMENTS

**⚠️ CRITICAL**: Citation API returns METADATA only, NOT actual documents.
After retrieving citation details, use PFW MCP to get office action documents.

**Step 1: Get Document List (Always Required)**
```python
# Use selective filtering to avoid context explosion
docs = pfw_get_application_documents(
    app_number='17896175',  # from citation['patentApplicationNumber']
    document_code='CTFR',   # See decoder below
    limit=20
)
```

**Document Code Decoder (Citation-Related Documents):**
- **CTFR**: Non-Final Office Action (where citation appears)
- **CTNF**: Final Office Action Rejection
- **NOA**: Notice of Allowance (citation overcame or not used)
- **892**: Examiner's Search Strategy & Citations List
- **IDS**: Applicant's Information Disclosure Statement

**Step 2a: LLM Analysis (Extract Text)**
```python
# When user asks: "What did the examiner say?" or "Why was this cited?"
content = pfw_get_document_content(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
# Analyze extracted text and answer user's question
```

**Step 2b: User Download (Provide PDF Link)**
```python
# When user says: "Get me the office action" or "I want to review it"
download = pfw_get_document_download(
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

pfw_apps = pfw_search_applications_minimal(
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
citation_data = []
for app in pfw_apps['applications'][:20]:  # Limit to prevent token explosion
    citations = search_citations_minimal(
        criteria=f"patentApplicationNumber:{app['applicationNumberText']} AND officeActionDate:[2017-10-01 TO *]",
        fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'citedDocumentIdentifier'],
        rows=50
    )
    citation_data.append({
        'app_number': app['applicationNumberText'],
        'citation_count': citations['response']['numFound'],
        'citations': citations['response']['docs']
    })
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
xml_data = pfw_get_patent_or_application_xml(
    application_number='17896175',
    include_fields=['abstract', 'claims'],  # Select only needed fields
    include_raw_xml=False  # ⭐ CRITICAL: 91-99% token reduction!
)
# Without include_raw_xml=False: ~50KB of raw XML included
# With include_raw_xml=False: ~4.5KB (91% reduction)
```

**When to Use XML vs Document Retrieval:**

| Use Case | Recommended Tool | Reason |
|----------|------------------|---------|
| Citation context & examiner reasoning | **pfw_get_application_documents** + **pfw_get_document_content** | Office action documents contain citations |
| Claim text for prior art comparison | **pfw_get_patent_or_application_xml** (include_fields=['claims'], include_raw_xml=False) | Structured claim data from patent XML |
| Patent abstract/description | **pfw_get_patent_or_application_xml** (include_fields=['abstract', 'description'], include_raw_xml=False) | Structured patent content |
| Examiner's citation decisions | **pfw_get_application_documents** (document_code='892') | 892 document lists examiner citations |

**Key Points:**
- Always use `include_raw_xml=False` (saves ~45KB per request, 91% reduction)
- For citations workflow, **document retrieval is preferred** over XML retrieval
- `include_fields=['citations']` has limited utility since Citations MCP already provides comprehensive citation metadata
- XML tool is best for patent content (claims, abstract), not citation context"""


def _get_workflows_ptab_section() -> str:
    """PTAB + Citation integration workflows"""
    return """## Citation + PTAB Integration Workflows

### Prior Art Validation for PTAB Challenges

**Use Case**: Validate prior art cited in IPR/PGR proceedings against prosecution history.

**Workflow:**
```python
# STEP 1: PTAB - Get IPR proceedings for patent (ultra-minimal mode for 99% reduction)
# Note: PTAB API now has separate search tools for trials, appeals, and interferences
# - Trials: search_trials_minimal/balanced/complete (IPR/PGR/CBM proceedings)
# - Appeals: search_appeals_minimal/balanced/complete (Ex Parte/Interference Appeals)
# - Interferences: search_interferences_minimal/balanced/complete (Derivations/Interferences)
# - Documents: ptab_get_documents(identifier, identifier_type) for all proceeding types
#
# Token Optimization: All search tools support `fields` parameter for ultra-minimal queries:
# - Ultra-minimal (2-3 fields): 99% reduction - Use for identifier correlation
# - Preset minimal (10-15 fields): 68% reduction - Use for discovery/presentation
# - Preset balanced (30-50 fields): 13.5% reduction - Use for detailed analysis

ptab_proceedings = search_trials_minimal(
    patent_number='9049188',
    fields=['trialNumber', 'trialMetaData.trialStatusCategory', 'patentOwnerData.patentNumber'],
    limit=20
)

# STEP 2: Citation - Get prosecution citations
citations = search_citations_balanced(
    criteria=f'publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
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
    citations = search_citations_minimal(
        criteria=f'publicationNumber:{patent} AND officeActionDate:[2017-10-01 TO *]',
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
- Use for: PTAB challenge research for cited patents"""


def _get_workflows_fpd_section() -> str:
    """FPD + Citation integration workflows"""
    return """## Citation + FPD Integration Workflows

### Petition Red Flags in Prosecution Quality

**Use Case**: Correlate petition filing with citation patterns to identify prosecution quality issues.

**Workflow:**
```python
# STEP 1: FPD - Get petitions for application
petitions = fpd_search_petitions_minimal(
    application_number='17896175',
    limit=10
)

# STEP 2: Citation - Get citation patterns
citations = search_citations_balanced(
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
citations = search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=200
)

# Get FPD petitions for same art unit
petitions = fpd_search_petitions_minimal(
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
- Use for: Petition research for cited applications"""


def _get_workflows_complete_section() -> str:
    """Four-MCP complete lifecycle analysis"""
    return """## Complete Prosecution Lifecycle Analysis

### Four-MCP Integration: Citation + PFW + PTAB + FPD

**Use Case**: Comprehensive patent intelligence from filing through post-grant.

**Complete Workflow:**

```python
# PHASE 1: Citation Intelligence
citations = search_citations_balanced(
    criteria=f'publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

examiner_citations = [c for c in citations['response']['docs']
                      if c['examinerCitedReferenceIndicator'] == 'true']

# PHASE 2: Prosecution History (PFW)
pfw_search = pfw_search_applications_minimal(
    query='patentNumber:9049188',
    fields=['applicationNumberText'],
    limit=1
)
app_number = pfw_search['applications'][0]['applicationNumberText']

# Get key prosecution documents
noa_docs = pfw_get_application_documents(
    app_number=app_number,
    document_code='NOA',
    limit=5
)

rejection_docs = pfw_get_application_documents(
    app_number=app_number,
    document_code='CTFR|CTNF',
    limit=10
)

# PHASE 3: Petition Analysis (FPD)
petitions = fpd_search_petitions_minimal(
    application_number=app_number,
    limit=10
)

# PHASE 4: PTAB Challenges (ultra-minimal mode for 99% reduction)
ptab_proceedings = search_trials_minimal(
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
- **Total: ~70KB (93% reduction)**"""


def _get_citation_codes_section() -> str:
    """Citation category decoder and strategic guidance"""
    return """## Citation Category Codes (X/Y/A/NPL)

### Category Definitions

**X - US Patents (§102/103 basis)**
- Primary prior art for US applications
- Used for anticipation (§102) or obviousness (§103) rejections
- Most common category in prosecution

**Y - Foreign Patents (§102/103 basis)**
- Foreign patent documents
- Often combined with X citations for obviousness
- Indicates international prior art landscape

**A - Additional References**
- Supplementary references
- Less critical to rejection
- Background art or supporting references

**NPL - Non-Patent Literature**
- Technical papers, articles, standards
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

**NPL Citations Present**
- Examiner performed thorough search
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
search_citations_minimal(
    criteria='citationCategoryCode:X AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# Get NPL citations (bleeding-edge tech)
search_citations_minimal(
    criteria='citationCategoryCode:NPL AND techCenter:2100',
    rows=50
)

# Get examiner citations only
search_citations_minimal(
    criteria='examinerCitedReferenceIndicator:true AND officeActionDate:[2023-01-01 TO *]',
    rows=100
)
```"""


def _get_data_coverage_section() -> str:
    """Data coverage and date handling guidance"""
    return """## Data Coverage (2017+ Eligibility)

### API Data Availability

**Office Action Dates:**
- **Start**: October 1, 2017
- **End**: 30 days prior to current date
- **Coverage**: ~7 years of citation data

**⚠️ CRITICAL DATE CONSTRAINT**
Office action dates before 2017-10-01 return NO results.
This is an API limitation, not a query error.

### Date Handling Strategies

**For Application-Based Searches:**
Use filing date starting 2015-01-01 to account for 1-2 year lag.

```python
# ✅ CORRECT: Account for filing-to-OA lag
search_citations_minimal(
    application_number='17896175',  # Filed 2015
    date_start='2015-01-01'          # Filing date context
)
# Will find citations from office actions mailed 2017+
```

**For Direct Citation Searches:**
Always use 2017-10-01 or later.

```python
# ✅ CORRECT: Direct citation date search
search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# ❌ WRONG: Date before API cutoff
search_citations_minimal(
    criteria='officeActionDate:[2015-01-01 TO 2024-12-31]',
    rows=100
)
# Returns warning: "Office action dates before 2017-10-01 not available"
```

### Filing-to-Office Action Timeline

**Typical Progression:**
- Filing date: 2015-01-01
- First office action: 2017-01-01 to 2018-01-01 (2-3 years)
- Citation data: Available if office action mailed 2017-10-01+

**Coverage Window:**
- Apps filed 2015+ → Office actions 2017+ → ✅ Citation data available
- Apps filed 2013-2014 → Office actions 2015-2016 → ❌ Citation data NOT available

### Cross-MCP Date Coordination

**PFW + Citations Integration:**
```python
# Use 2015-01-01 for PFW filing date filter
pfw_apps = pfw_search_applications_minimal(
    query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
    fields=['applicationNumberText'],
    limit=50
)

# Always include officeActionDate constraint for citations
for app in pfw_apps:
    citations = search_citations_minimal(
        criteria=f'patentApplicationNumber:{app} AND officeActionDate:[2017-10-01 TO *]',
        rows=50
    )
```

### Eligibility Quick Check

**Use Cases:**

| Scenario | Filing Date | First OA Date | Citations Available? |
|----------|-------------|---------------|---------------------|
| Recent app | 2020-01-01 | 2022-01-01 | ✅ Yes |
| Older app | 2015-01-01 | 2017-06-01 | ✅ Yes |
| Pre-2015 app | 2014-01-01 | 2016-06-01 | ❌ No |
| Very old app | 2010-01-01 | 2012-06-01 | ❌ No |

**For examiner analysis:** Use 2015-01-01 filing date to capture last ~10 years of work (vs entire 20-30 year career), saving massive context."""


def _get_fields_section() -> str:
    """Field selection strategies and Solr/Lucene syntax"""
    return """## Field Selection Strategies

### Predefined Field Sets

**citations_minimal (8 fields):**
- `citationIdentifier`
- `patentApplicationNumber`
- `publicationNumber`
- `groupArtUnitNumber`
- `citationCategoryCode`
- `techCenter`
- `officeActionDate`
- `examinerCitedReferenceIndicator`

**citations_balanced (18 fields):**
All minimal fields plus:
- `citedDocumentIdentifier`
- `citingPassageText`
- `relatedClaimNumberText`
- `officeActionCategory`
- `nplIndicator`
- Additional metadata fields

### Ultra-Minimal Mode (Custom Fields)

**99% Token Reduction Examples:**

```python
# For PFW integration (2 fields only)
search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier', 'patentApplicationNumber'],
    rows=100
)
# Token cost: ~10KB (vs ~400KB with preset minimal)

# For frequency analysis (1 field only!)
search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier'],
    rows=500
)
# Token cost: ~25KB (vs ~2MB with preset minimal)

# For examiner behavior (3 fields)
search_citations_minimal(
    criteria='officeActionDate:[2023-01-01 TO *]',
    fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=200
)
# Token cost: ~20KB (vs ~800KB with preset minimal)
```

### Solr/Lucene Query Syntax

**Field Searches:**
```
patentApplicationNumber:18010777        # Exact match
groupArtUnitNumber:2854                 # Art unit
techCenter:2100                         # Technology center
citedDocumentIdentifier:US*             # Wildcard
publicationNumber:11234567              # Patent number
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
nplIndicator:true                                      # NPL only
citationCategoryCode:NPL                               # Category code
```

### Common Query Patterns

**Examiner Citation Analysis:**
```python
search_citations_minimal(
    criteria='examinerCitedReferenceIndicator:true AND groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)
```

**Technology Landscape:**
```python
search_citations_minimal(
    criteria='techCenter:2100 AND citationCategoryCode:X AND officeActionDate:[2023-01-01 TO *]',
    rows=100
)
```

**NPL Analysis:**
```python
search_citations_minimal(
    criteria='citationCategoryCode:NPL AND techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=50
)
```"""


def _get_errors_section() -> str:
    """Common error patterns and troubleshooting"""
    return """## Common Errors and Troubleshooting

### Date Range Errors

**Error**: "No results found" or "Office action dates before 2017-10-01 not available"

**Cause**: Searching before API cutoff date (2017-10-01)

**Solution:**
```python
# ❌ WRONG
search_citations_minimal(date_start='2015-01-01', date_end='2024-12-31')

# ✅ CORRECT
search_citations_minimal(date_start='2017-10-01', date_end='2024-12-31')

# ✅ CORRECT (for application searches, use filing date context)
search_citations_minimal(
    application_number='17896175',  # Filed 2015
    date_start='2015-01-01'          # Will search citations from 2017+
)
```

### Field Name Errors

**Error**: "Field not found" or 400 Bad Request

**Cause**: Invalid field names in query or fields parameter

**Solution**: Use `get_available_fields()` to discover valid field names

```python
# Get all available fields
fields_info = get_available_fields()

# Check field names before using in query
```

### Query Syntax Errors

**Error**: "Invalid query syntax" or parsing errors

**Cause**: Malformed Solr/Lucene query syntax

**Solution**: Use `validate_query()` before execution

```python
# Validate complex query
validation = validate_query(
    query='citationCategoryCode:X AND techCenter:2100 NOT groupArtUnitNumber:1600'
)

if validation['valid']:
    # Proceed with search
    search_citations_minimal(criteria=query, rows=100)
```

### Cross-MCP Integration Errors

**Error**: "Application number not found" when integrating with PFW

**Cause**: Application filed before 2015 or office action before 2017-10-01

**Solution**: Check filing date and office action date eligibility

```python
# STEP 1: Check PFW filing date
pfw_app = pfw_search_applications_minimal(
    application_number='12345678',
    fields=['applicationNumberText', 'applicationMetaData.filingDate']
)

filing_date = pfw_app['applications'][0]['applicationMetaData']['filingDate']

# STEP 2: Only search citations if filing date >= 2015-01-01
if filing_date >= '2015-01-01':
    citations = search_citations_minimal(
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
1. Validate query syntax with `validate_query()`
2. Check date range is within 2017-10-01 to present
3. Broaden search criteria to verify data exists
4. Check field names with `get_available_fields()`"""


def _get_cost_section() -> str:
    """Cost optimization strategies"""
    return """## Cost Optimization Strategies

### Token Efficiency Hierarchy

**Level 1: Ultra-Minimal Mode (99% reduction)**
```python
# 1-2 fields for frequency/discovery
search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier'],  # Only 1 field!
    rows=500
)
# Token cost: ~25KB (vs ~2MB with preset minimal)
```

**Level 2: Preset Minimal (90-95% reduction)**
```python
# 8 preset fields for discovery
search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)
# Token cost: ~40KB
```

**Level 3: Custom Minimal (75-90% reduction)**
```python
# 3-5 custom fields for targeted analysis
search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'patentApplicationNumber'],
    rows=100
)
# Token cost: ~15KB
```

**Level 4: Balanced (70-80% reduction)**
```python
# 18 preset fields for comprehensive analysis
search_citations_balanced(
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
- Use balanced or get_citation_details
- Low volume (5-10 results)
- Complete analysis of final selections
- Cost: ~20-50KB

**Total Cost: ~40-125KB vs 500KB-2MB without optimization**

### Cross-MCP Optimization

**PFW + Citations Integration:**
```python
# Ultra-efficient workflow
# STEP 1: PFW discovery (1 field only)
pfw_apps = pfw_search_applications_minimal(
    query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
    fields=['applicationNumberText'],  # Only app numbers!
    limit=50
)
# Cost: ~2-3KB

# STEP 2: Citation analysis (3 fields, top 20 only)
for app in pfw_apps['applications'][:20]:
    citations = search_citations_minimal(
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
search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citationCategoryCode', 'groupArtUnitNumber'],
    rows=200
)

# ❌ AVOID: Open-ended searches without field limits
search_citations_balanced(
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
5. Limit cross-MCP integration to top 20 items"""


def get_all_reflections() -> str:
    """Get all tool reflections and guidance (legacy compatibility)."""
    return """# USPTO Enriched Citation API v3 - Complete Tool Guidance

⚠️ **DEPRECATION NOTICE**: This function returns all guidance at once (~62KB).
For 90-95% token reduction, use `citations_get_guidance(section)` instead.

Use `citations_get_guidance("overview")` to see available sections and quick reference chart.

""" + _get_overview_section()


# Legacy function for backward compatibility
def get_tool_reflections(workflow_type: str = "general") -> str:
    """
    Legacy function for backward compatibility.

    ⚠️ **DEPRECATED**: Use citations_get_guidance(section) instead.

    This function provides workflow-based guidance but is less efficient than
    the sectioned approach. New code should use citations_get_guidance().
    """
    # Map old workflow types to new sections
    workflow_map = {
        "cross_mcp": "workflows_complete",
        "litigation": "workflows_complete",
        "prosecution": "workflows_pfw",
        "portfolio": "workflows_complete",
        "general": "overview"
    }

    section = workflow_map.get(workflow_type, "overview")

    return f"""# USPTO Enriched Citation MCP - Workflow Guidance

⚠️ **DEPRECATION NOTICE**: get_tool_reflections() is deprecated.
Use `citations_get_guidance("{section}")` for better context efficiency.

{_get_overview_section()}
"""
