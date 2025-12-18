# USPTO Enriched Citation MCP Usage Examples

This document provides comprehensive examples for using the USPTO Enriched Citation MCP, including progressive disclosure patterns, cross-MCP integration workflows, ultra-minimal mode optimization, and examiner citation analysis strategies.

## Notes on Enriched Citation MCP Usage

For the most part, **the LLMs will perform these searches and workflows on their own with minimal guidance from the user**. These examples are illustrative to give insight into what the LLMs are doing in the background.

**💡 Best Practice Recommendation:** For complex workflows or when you're unsure about the best approach, start by asking the LLM to use the `citations_get_guidance` tool first. This tool provides context-efficient workflow recommendations and helps the LLM choose the most appropriate tools and strategies for your specific use case.

Sample requests that the user can give to the LLM to trigger the examples are as follows:

### Sample User Requests by Example

**Example 1 - Progressive Disclosure Workflow:**
- *"Find all citations for patent 9049188"*
- *"Analyze citation patterns for application 17896175"*
- *"Show me what prior art the examiner cited for this patent"*

**Example 2 - Ultra-Minimal Mode (99% Token Reduction):**
- *"Get citation counts for these 100 applications without using too much context"*
- *"I need just the citation identifiers for this patent"*
- *"Extract only patent numbers from citations for art unit 2854"*

**Example 3 - Examiner Citation Pattern Analysis:**
- *"Analyze examiner Smith's citation behavior across their applications"*
- *"Show me which examiners in art unit 2128 cite the most NPL"*
- *"What citation patterns does examiner Johnson prefer?"*

**Example 4 - Citation Category Analysis (X/Y/A/NPL):**
- *"Show me the breakdown of X vs Y vs NPL citations for this patent"*
- *"Which citations were most critical to patentability?"*
- *"Analyze the category distribution for art unit 3600"*

**Example 5 - Prior Art Landscape Mapping:**
- *"Map the prior art landscape for technology center 2100"*
- *"Which patents are cited most frequently in AI applications?"*
- *"Show me citation trends in art unit 2854 over the last 3 years"*

**Example 6 - Art Unit Citation Norms:**
- *"What's the average citation count for art unit 1759?"*
- *"Compare citation patterns across different art units"*
- *"Identify art units with high NPL usage"*

**Example 7-10 - Cross-MCP Integration Workflows:**
- *"Analyze this examiner's citation patterns and prosecution history"*
- *"Compare prosecution citations with PTAB prior art for patent 9049188"*
- *"Do a complete due diligence check including citations for this patent"*
- *"Check if applications with petition red flags have unusual citation patterns"*

## Table of Contents
1. [Progressive Disclosure Workflow](#-example-1-progressive-disclosure-workflow)
2. [Ultra-Minimal Mode (99% Token Reduction)](#-example-2-ultra-minimal-mode-99-token-reduction)
3. [Examiner Citation Pattern Analysis](#-example-3-examiner-citation-pattern-analysis-pfw--citations)
4. [Citation Category Analysis (X/Y/A/NPL)](#-example-4-citation-category-analysis-xyanpl)
5. [Prior Art Landscape Mapping](#-example-5-prior-art-landscape-mapping)
6. [Art Unit Citation Norms](#-example-6-art-unit-citation-norms)
7. [Cross-MCP Integration with PFW](#-example-7-cross-mcp-integration-with-pfw)
8. [Cross-MCP Integration with PTAB](#-example-8-cross-mcp-integration-with-ptab)
9. [Cross-MCP Integration with FPD](#-example-9-cross-mcp-integration-with-fpd)
10. [Complete Lifecycle Analysis](#-example-10-complete-lifecycle-analysis-four-mcp-integration)
11. [Known Patents for Testing](#known-patents-for-testing)
12. [Full Tool Reference](#full-tool-reference)

---

### ⭐ Example 1: Progressive Disclosure Workflow

The Citations MCP uses a **progressive disclosure pattern** to optimize token usage. Start with minimal searches for discovery, then escalate to balanced or detailed analysis only for selected citations.

#### Stage 1: Discovery with Minimal Search (90-95% Token Reduction)

```python
# Fast discovery: Find all citations for a patent
discovery = search_citations_minimal(
    criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    rows=50
)

print(f"Found {discovery['response']['numFound']} citations")
print(f"Returned {len(discovery['response']['docs'])} results")

# Present top citations to user
for citation in discovery['response']['docs'][:10]:
    print(f"{citation['citedDocumentIdentifier']}: {citation['citationCategoryCode']}")
```

**Minimal Search Fields (8 fields):**
- `citedDocumentIdentifier` - Patent/publication number cited
- `patentApplicationNumber` - Application where citation appears
- `publicationNumber` - Published patent number
- `citationCategoryCode` - X/Y/A/NPL category
- `examinerCitedReferenceIndicator` - Examiner vs applicant
- `groupArtUnitNumber` - Art unit
- `techCenter` - Technology center
- `officeActionDate` - When citation was made

**Token Efficiency:**
- Minimal (8 fields): ~400 chars/result
- 50 results: ~20KB total
- **90-95% reduction vs full data**

#### Stage 2: Analysis with Balanced Search (70-80% Token Reduction)

```python
# After user selects 10 citations of interest, get detailed analysis
balanced = search_citations_balanced(
    criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    rows=10
)

# Analyze with full context
for citation in balanced['response']['docs']:
    print(f"Citation: {citation['citedDocumentIdentifier']}")
    print(f"  Category: {citation['citationCategoryCode']}")
    print(f"  Examiner cited: {citation['examinerCitedReferenceIndicator']}")
    print(f"  Related claims: {citation.get('relatedClaimNumberText', 'N/A')}")
    print(f"  Passage: {citation.get('passageLocationText', 'N/A')}")
    print(f"  Office Action: {citation.get('officeActionCategory', 'N/A')}")
```

**Balanced Search Fields (18+ fields):**
- All minimal fields PLUS:
- `relatedClaimNumberText` - Claims cited against
- `passageLocationText` - Specific sections cited
- `officeActionCategory` - Office action type
- `workGroupNumber` - Work group
- Additional classification and cross-reference fields

**Token Efficiency:**
- Balanced (18 fields): ~2,000 chars/result
- 10 results: ~20KB total
- **70-80% reduction vs full data**

#### Stage 3: Details for Specific Citations

```python
# For 1-5 strategically important citations, get complete details
citation_details = get_citation_details(
    citation_id='12345678-abcd-1234-abcd-123456789abc'
)

print(f"Complete citation record:")
print(f"  Cited patent: {citation_details['citedDocumentIdentifier']}")
print(f"  Application: {citation_details['patentApplicationNumber']}")
print(f"  Full passage context: {citation_details.get('passageLocationText', 'N/A')}")
```

**Progressive Workflow Summary:**
1. **Discovery (50-100 results)**: Minimal fields, identify patterns
2. **Selection**: User/AI selects 10-20 relevant citations
3. **Analysis (10-20 results)**: Balanced fields, detailed review
4. **Details (1-5 results)**: Complete records for critical citations

**Total Token Savings: ~93% vs fetching full data upfront**

---

### 🚀 Example 2: Ultra-Minimal Mode (99% Token Reduction)

**NEW in v2.1+**: All search tools now support an optional `fields` parameter for maximum token efficiency. Override preset fields to get only what you need.

#### Custom Fields Parameter

```python
# Standard minimal search (8 fields, 95% reduction)
standard_minimal = search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)
# Returns: 8 fields × 100 results = ~40KB

# Ultra-minimal search (2 fields, 99% reduction)
ultra_minimal = search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier', 'citationCategoryCode'],  # Only 2 fields!
    rows=100
)
# Returns: 2 fields × 100 results = ~8KB (99% reduction!)
```

#### Use Cases for Ultra-Minimal Mode

**1. Citation Counting and Statistics**
```python
# Get just citation counts by category
citation_counts = search_citations_minimal(
    criteria='patentApplicationNumber:17896175 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citationCategoryCode'],  # Single field
    rows=100
)

# Analyze category distribution
from collections import Counter
categories = Counter([c['citationCategoryCode'] for c in citation_counts['response']['docs']])
print(f"X citations: {categories['X']}")
print(f"Y citations: {categories['Y']}")
print(f"NPL citations: {categories['NPL']}")
```

**2. Cited Patent Extraction**
```python
# Extract only patent numbers for prior art list
prior_art_list = search_citations_minimal(
    criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    fields=['citedDocumentIdentifier'],  # Single field
    rows=50
)

cited_patents = [c['citedDocumentIdentifier'] for c in prior_art_list['response']['docs']]
print(f"Prior art references: {', '.join(cited_patents[:10])}")
```

**3. Cross-MCP Integration Prep**
```python
# Get minimal data for PFW integration (3 fields only)
citation_prep = search_citations_minimal(
    criteria='groupArtUnitNumber:1759 AND officeActionDate:[2017-10-01 TO *]',
    fields=[
        'patentApplicationNumber',  # For PFW lookup
        'citedDocumentIdentifier',   # Citation reference
        'citationCategoryCode'       # Category
    ],
    rows=50
)
# Result: ~10KB for 50 results (99% reduction vs full data)
```

**Token Efficiency Comparison:**
```
Scenario: Search 100 citations for art unit analysis

Ultra-minimal (2 fields):
  ~80 chars/result × 100 = ~8KB total (99% reduction)

Preset minimal (8 fields):
  ~400 chars/result × 100 = ~40KB total (95% reduction)

Preset balanced (18 fields):
  ~2,000 chars/result × 100 = ~200KB total (80% reduction)

Full with all fields (NEVER):
  ~10,000 chars/result × 100 = ~1MB total (unusable)
```

**When to Use Custom Fields:**
- **High-volume extraction**: 100+ results where only 1-3 fields needed
- **Citation statistics**: Category counts, examiner ratios
- **Prior art lists**: Extract cited document identifiers only
- **Cross-MCP prep**: Minimal fields for PFW/PTAB/FPD integration
- **Performance optimization**: Maximum speed with minimal data

**When to Use Preset Fields:**
- **User selection workflows**: Need titles, categories, art units for user to choose
- **Analysis workflows**: Need metadata for pattern analysis
- **First-time exploration**: Don't know which fields you'll need yet

---

### 👨‍⚖️ Example 3: Examiner Citation Pattern Analysis (PFW → Citations)

**⚠️ CRITICAL**: The Citation API does **NOT** contain examiner name fields. You **MUST** use a two-step PFW → Citations workflow for examiner analysis.

#### Two-Step Workflow with Ultra-Minimal Optimization

```python
# STEP 1: PFW - Get examiner's applications (wildcard-first strategy)
examiner_last_name = 'SMITH'  # Extract from "SMITH, JANE"

# Ultra-minimal PFW search (3 fields only, 99% token reduction)
pfw_apps = pfw_search_applications_minimal(
    query=f'examinerNameText:{examiner_last_name}* AND filingDate:[2015-01-01 TO *]',
    fields=[
        'applicationNumberText',
        'examinerNameText',
        'groupArtUnitNumber'
    ],  # ONLY 3 fields
    limit=50
)
# Result: ~5KB for 50 apps (vs ~25KB with preset minimal, ~500KB with full data)

print(f"Found {len(pfw_apps['applications'])} applications by {examiner_last_name}*")

# STEP 2: Analyze art unit distribution (wildcard returns multiple examiners)
from collections import Counter
art_unit_dist = Counter([app['groupArtUnitNumber'] for app in pfw_apps['applications']])
print(f"Art unit distribution: {art_unit_dist}")

# STEP 3: Get citations for top 20 applications (prevent token explosion)
citation_data = []
for app in pfw_apps['applications'][:20]:  # Limit to 20 apps
    citations = search_citations_minimal(
        criteria=f"patentApplicationNumber:{app['applicationNumberText']} AND officeActionDate:[2017-10-01 TO *]",
        fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'citedDocumentIdentifier'],
        rows=50
    )

    citation_data.append({
        'app_number': app['applicationNumberText'],
        'examiner': app['examinerNameText'],
        'art_unit': app['groupArtUnitNumber'],
        'citation_count': citations['response']['numFound'],
        'citations': citations['response']['docs']
    })

# STEP 4: Analyze examiner citation patterns
total_citations = sum(item['citation_count'] for item in citation_data)
examiner_citations = sum(
    sum(1 for c in item['citations'] if c.get('examinerCitedReferenceIndicator') == 'true')
    for item in citation_data
)

print(f"\nEXAMINER CITATION ANALYSIS")
print(f"=========================")
print(f"Applications analyzed: {len(citation_data)}")
print(f"Total citations: {total_citations}")
print(f"Examiner citations: {examiner_citations}")
print(f"Applicant citations: {total_citations - examiner_citations}")
print(f"Examiner citation rate: {examiner_citations/total_citations*100:.1f}%")

# Analyze citation categories
all_citations = [c for item in citation_data for c in item['citations']]
category_dist = Counter([c['citationCategoryCode'] for c in all_citations])
print(f"\nCitation Category Distribution:")
print(f"  X (US patents - critical): {category_dist['X']}")
print(f"  Y (Foreign patents): {category_dist.get('Y', 0)}")
print(f"  A (Background): {category_dist.get('A', 0)}")
print(f"  NPL (Non-patent literature): {category_dist.get('NPL', 0)}")
```

**Why This Workflow Works:**
1. **Wildcard Strategy**: `SMITH*` finds all SMITH variants (SMITH, JOHN; SMITH, JANE; etc.)
2. **Ultra-Minimal Fields**: Request only 3 fields from PFW (99% token reduction)
3. **Date Filtering**: `filingDate:[2015-01-01 TO *]` accounts for 2-year lag to office action (Oct 2017+ coverage)
4. **Progressive Limiting**: Analyze only top 20 apps to prevent token explosion
5. **Custom Citation Fields**: Request only 3 citation fields for pattern analysis

**Token Efficiency Summary:**
- PFW ultra-minimal: 50 apps × 3 fields = ~5KB
- Citations ultra-minimal: 1000 citations × 3 fields = ~60KB
- **Total: ~65KB vs ~2.5MB without optimization = 97% savings**

---

### 📊 Example 4: Citation Category Analysis (X/Y/A/NPL)

#### Citation Category Codes

**X - US Patents (§102/103 basis)**
- Most relevant to patentability
- Critical prior art for rejection/allowance
- Primary focus for invalidity analysis

**Y - Foreign Patents**
- Relevant to patentability but not US patents
- Important for international prior art

**A - Background References**
- US patents for context only
- Not basis for rejection
- Background/understanding material

**NPL - Non-Patent Literature**
- Scientific papers, technical documents
- Often indicates sophisticated prior art search
- Critical for AI/software/biotech fields

#### Category Distribution Analysis

```python
# Get all citations for patent with category breakdown
citations = search_citations_balanced(
    criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# Analyze category distribution
from collections import Counter
categories = Counter([c['citationCategoryCode'] for c in citations['response']['docs']])

# Calculate examiner vs applicant for each category
examiner_by_category = {}
applicant_by_category = {}

for citation in citations['response']['docs']:
    category = citation['citationCategoryCode']
    is_examiner = citation.get('examinerCitedReferenceIndicator') == 'true'

    if is_examiner:
        examiner_by_category[category] = examiner_by_category.get(category, 0) + 1
    else:
        applicant_by_category[category] = applicant_by_category.get(category, 0) + 1

print(f"CITATION CATEGORY ANALYSIS")
print(f"=========================")
print(f"Total citations: {citations['response']['numFound']}")
print(f"\nCategory Breakdown:")
print(f"  X (US - critical): {categories['X']} (Examiner: {examiner_by_category.get('X', 0)}, Applicant: {applicant_by_category.get('X', 0)})")
print(f"  Y (Foreign): {categories.get('Y', 0)} (Examiner: {examiner_by_category.get('Y', 0)}, Applicant: {applicant_by_category.get('Y', 0)})")
print(f"  A (Background): {categories.get('A', 0)} (Examiner: {examiner_by_category.get('A', 0)}, Applicant: {applicant_by_category.get('A', 0)})")
print(f"  NPL (Non-patent): {categories.get('NPL', 0)} (Examiner: {examiner_by_category.get('NPL', 0)}, Applicant: {applicant_by_category.get('NPL', 0)})")
```

#### Strategic Indicators

**High Quality Prosecution:**
- High X citation count (10+ from examiner)
- NPL citations present (sophisticated search)
- Balanced examiner vs applicant ratio

**Potential Vulnerability:**
- Low X citation count (<5 from examiner)
- No NPL citations (narrow search)
- High applicant-only citations (IDS not reviewed)

---

### 🗺️ Example 5: Prior Art Landscape Mapping

#### Technology Area Citation Trends

```python
# Map citation landscape for technology center 2100 (AI/software)
tech_citations = search_citations_minimal(
    criteria='techCenter:2100 AND officeActionDate:[2020-01-01 TO *]',
    fields=['citedDocumentIdentifier', 'citationCategoryCode', 'officeActionDate'],
    rows=200
)

# Find most frequently cited patents
citation_freq = Counter([c['citedDocumentIdentifier'] for c in tech_citations['response']['docs']])

print(f"PRIOR ART LANDSCAPE - Tech Center 2100")
print(f"=====================================")
print(f"Total citations: {tech_citations['response']['numFound']}")
print(f"\nMost Cited Patents:")
for patent, count in citation_freq.most_common(10):
    print(f"  {patent}: {count} citations")
```

#### Art Unit Citation Comparison

```python
# Compare citation patterns across art units
art_units = ['2854', '1759', '3600']
comparison = {}

for art_unit in art_units:
    citations = search_citations_minimal(
        criteria=f'groupArtUnitNumber:{art_unit} AND officeActionDate:[2020-01-01 TO *]',
        fields=['citationCategoryCode', 'examinerCitedReferenceIndicator', 'patentApplicationNumber'],
        rows=200
    )

    unique_apps = len(set(c['patentApplicationNumber'] for c in citations['response']['docs']))
    avg_citations = citations['response']['numFound'] / unique_apps if unique_apps > 0 else 0

    category_dist = Counter([c['citationCategoryCode'] for c in citations['response']['docs']])
    npl_percentage = (category_dist.get('NPL', 0) / citations['response']['numFound'] * 100) if citations['response']['numFound'] > 0 else 0

    comparison[art_unit] = {
        'total_citations': citations['response']['numFound'],
        'unique_apps': unique_apps,
        'avg_per_app': avg_citations,
        'npl_percentage': npl_percentage
    }

print(f"\nART UNIT COMPARISON")
print(f"==================")
for art_unit, stats in comparison.items():
    print(f"\nArt Unit {art_unit}:")
    print(f"  Total citations: {stats['total_citations']}")
    print(f"  Unique applications: {stats['unique_apps']}")
    print(f"  Avg citations/app: {stats['avg_per_app']:.1f}")
    print(f"  NPL usage: {stats['npl_percentage']:.1f}%")
```

---

### 📈 Example 6: Art Unit Citation Norms

#### Statistical Analysis for Prosecution Strategy

```python
# Get statistical norms for art unit 2854
art_unit_stats = get_citation_statistics(
    query='groupArtUnitNumber:2854 AND officeActionDate:[2020-01-01 TO *]'
)

print(f"ART UNIT 2854 CITATION NORMS")
print(f"============================")
print(f"Total citations: {art_unit_stats.get('numFound', 0)}")

# Get detailed citations for analysis
citations = search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2020-01-01 TO *]',
    fields=['patentApplicationNumber', 'citationCategoryCode', 'examinerCitedReferenceIndicator'],
    rows=200
)

# Calculate metrics
unique_apps = len(set(c['patentApplicationNumber'] for c in citations['response']['docs']))
avg_citations_per_app = citations['response']['numFound'] / unique_apps

examiner_citations = sum(1 for c in citations['response']['docs']
                         if c.get('examinerCitedReferenceIndicator') == 'true')
examiner_percentage = (examiner_citations / citations['response']['numFound'] * 100)

category_dist = Counter([c['citationCategoryCode'] for c in citations['response']['docs']])

print(f"Applications analyzed: {unique_apps}")
print(f"Average citations per application: {avg_citations_per_app:.1f}")
print(f"Examiner citation rate: {examiner_percentage:.1f}%")
print(f"\nCategory Distribution:")
print(f"  X: {category_dist['X']} ({category_dist['X']/citations['response']['numFound']*100:.1f}%)")
print(f"  NPL: {category_dist.get('NPL', 0)} ({category_dist.get('NPL', 0)/citations['response']['numFound']*100:.1f}%)")
```

---

### 🔗 Example 7: Cross-MCP Integration with PFW

#### Citation Context Retrieval Workflow

**⚠️ CRITICAL**: Citation API returns METADATA only, NOT actual documents. Use PFW MCP to retrieve office action documents containing citation context.

```python
# STEP 1: Citations - Get citation metadata
citations = search_citations_balanced(
    criteria='patentApplicationNumber:17896175 AND officeActionDate:[2017-10-01 TO *]',
    rows=20
)

print(f"Found {citations['response']['numFound']} citations")

# STEP 2: PFW - Get office action documents (where citations appear)
# Use selective filtering to avoid context explosion
office_actions = pfw_get_application_documents(
    app_number='17896175',
    document_code='CTFR',  # Non-final office actions
    limit=10
)

print(f"Found {office_actions['count']} office action documents")

# STEP 3a: LLM Analysis - Extract text from office action
if office_actions['documents']:
    oa_content = pfw_get_document_content(
        app_number='17896175',
        document_identifier=office_actions['documents'][0]['documentIdentifier'],
        auto_optimize=True  # Free PyPDF2 → Mistral OCR fallback
    )

    print(f"\nOffice Action Analysis:")
    print(f"Extraction method: {oa_content['extraction_method']}")
    print(f"Content length: {len(oa_content['extracted_content'])} chars")
    # Analyze extracted text to understand citation context

# STEP 3b: User Download - Provide PDF link
download_link = pfw_get_document_download(
    app_number='17896175',
    document_identifier=office_actions['documents'][0]['documentIdentifier']
)

print(f"\n**📁 [Download Office Action ({download_link['pageCount']} pages)]({download_link['proxy_url']})**")
```

**Document Code Decoder (Citation-Related):**
- **CTFR**: Non-Final Office Action (where citation appears)
- **CTNF**: Final Office Action Rejection
- **NOA**: Notice of Allowance (citation overcame or not used)
- **892**: Examiner's Search Strategy & Citations List
- **IDS**: Applicant's Information Disclosure Statement

---

### ⚖️ Example 8: Cross-MCP Integration with PTAB

#### Prior Art Validation for IPR Challenges

```python
# STEP 1: PTAB - Get IPR proceedings for patent
ptab_proceedings = ptab_search_proceedings_balanced(
    patent_number='9049188',
    limit=10
)

print(f"Found {ptab_proceedings.get('recordTotalQuantity', 0)} PTAB proceedings")

# STEP 2: Citations - Get prosecution citations
prosecution_citations = search_citations_balanced(
    criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# Extract cited patent identifiers
prosecution_prior_art = set(c['citedDocumentIdentifier']
                            for c in prosecution_citations['response']['docs'])

print(f"\nProsecution Prior Art: {len(prosecution_prior_art)} unique references")

# STEP 3: Compare with PTAB prior art (would extract from PTAB documents)
# This example shows the workflow pattern
print(f"\nPTAB PRIOR ART ANALYSIS")
print(f"======================")
print(f"Prosecution citations: {len(prosecution_prior_art)}")
# In actual workflow, compare with PTAB petition prior art to identify new references
```

#### PTAB Vulnerability Assessment

```python
# Identify patents vulnerable to post-grant challenges based on citation patterns

portfolio_patents = ['9049188', '7971071', '11788453']  # Example portfolio
vulnerability_scores = {}

for patent in portfolio_patents:
    citations = search_citations_minimal(
        criteria=f'publicationNumber:{patent} AND officeActionDate:[2017-10-01 TO *]',
        fields=['examinerCitedReferenceIndicator', 'citationCategoryCode'],
        rows=100
    )

    # Calculate vulnerability indicators
    total_citations = citations['response']['numFound']
    examiner_citations = sum(1 for c in citations['response']['docs']
                             if c.get('examinerCitedReferenceIndicator') == 'true')
    npl_citations = sum(1 for c in citations['response']['docs']
                        if c['citationCategoryCode'] == 'NPL')

    # Vulnerability scoring
    vulnerability_score = 0
    if examiner_citations < 5:
        vulnerability_score += 3  # Minimal examiner search
    if npl_citations == 0:
        vulnerability_score += 2  # No NPL (narrow search scope)
    if total_citations < 10:
        vulnerability_score += 2  # Low overall citation count

    vulnerability_scores[patent] = {
        'total': total_citations,
        'examiner': examiner_citations,
        'npl': npl_citations,
        'vulnerability_score': vulnerability_score
    }

print(f"PTAB VULNERABILITY ASSESSMENT")
print(f"============================")
for patent, stats in vulnerability_scores.items():
    risk_level = "HIGH" if stats['vulnerability_score'] >= 5 else "MEDIUM" if stats['vulnerability_score'] >= 3 else "LOW"
    print(f"\nPatent {patent}:")
    print(f"  Total citations: {stats['total']}")
    print(f"  Examiner citations: {stats['examiner']}")
    print(f"  NPL citations: {stats['npl']}")
    print(f"  Vulnerability: {risk_level} (score: {stats['vulnerability_score']}/7)")
```

---

### 🚩 Example 9: Cross-MCP Integration with FPD

#### Petition Red Flags in Citation Patterns

```python
# STEP 1: FPD - Get petitions for application
petitions = fpd_search_petitions_minimal(
    application_number='17896175',
    limit=10
)

print(f"Found {petitions.get('recordTotalQuantity', 0)} petitions")

# STEP 2: Citations - Get citation patterns
citations = search_citations_balanced(
    criteria='patentApplicationNumber:17896175 AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# STEP 3: Analyze correlation
petition_count = petitions.get('recordTotalQuantity', 0)
citation_count = citations['response']['numFound']

print(f"\nPETITION-CITATION CORRELATION")
print(f"============================")
print(f"Petitions filed: {petition_count}")
print(f"Total citations: {citation_count}")

if petition_count > 0 and citation_count < 5:
    print(f"⚠️ RED FLAG: Petition filed with minimal prior art")
    print(f"   Possible examiner search quality issue")
elif petition_count > 1:
    print(f"⚠️ RED FLAG: Multiple petitions filed")
    print(f"   Review citation patterns for prosecution quality")
else:
    print(f"✅ Normal petition/citation correlation")
```

#### Art Unit Quality Assessment with Petition Correlation

```python
# Get art unit citation statistics
art_unit_citations = search_citations_minimal(
    criteria='groupArtUnitNumber:2854 AND officeActionDate:[2020-01-01 TO *]',
    fields=['examinerCitedReferenceIndicator', 'patentApplicationNumber', 'citationCategoryCode'],
    rows=200
)

# Get FPD petitions for same art unit
art_unit_petitions = fpd_search_petitions_minimal(
    art_unit='2854',
    limit=100
)

# Calculate quality metrics
unique_apps = len(set(c['patentApplicationNumber']
                     for c in art_unit_citations['response']['docs']))
citation_density = art_unit_citations['response']['numFound'] / unique_apps

# Petition rate (approximation based on available data)
petition_count = art_unit_petitions.get('recordTotalQuantity', 0)
petition_rate = petition_count / unique_apps if unique_apps > 0 else 0

print(f"ART UNIT 2854 QUALITY ASSESSMENT")
print(f"================================")
print(f"Unique applications: {unique_apps}")
print(f"Citation density: {citation_density:.1f} citations/app")
print(f"Petition rate: {petition_rate:.2f} petitions/app")

if petition_rate > 0.2 and citation_density < 3:
    print(f"\n⚠️ QUALITY CONCERN: High petition rate with low citation density")
    print(f"   May indicate prosecution or examiner quality issues")
```

---

### 🔄 Example 10: Complete Lifecycle Analysis (Four-MCP Integration)

#### Comprehensive Patent Intelligence: Filing → Prosecution → Petitions → Grant → PTAB

```python
patent_number = '9049188'

print(f"COMPLETE PATENT LIFECYCLE INTELLIGENCE")
print(f"=====================================")
print(f"Patent: {patent_number}\n")

# PHASE 1: Citation Intelligence
print(f"PHASE 1: CITATION INTELLIGENCE")
print(f"------------------------------")
citations = search_citations_balanced(
    criteria=f'publicationNumber:{patent_number} AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

total_citations = citations['response']['numFound']
examiner_citations = [c for c in citations['response']['docs']
                      if c.get('examinerCitedReferenceIndicator') == 'true']
category_dist = Counter([c['citationCategoryCode'] for c in citations['response']['docs']])

print(f"Total citations: {total_citations}")
print(f"Examiner citations: {len(examiner_citations)}")
print(f"Category breakdown:")
print(f"  X (critical): {category_dist['X']}")
print(f"  NPL: {category_dist.get('NPL', 0)}")

# PHASE 2: Prosecution History (PFW)
print(f"\nPHASE 2: PROSECUTION HISTORY (PFW)")
print(f"----------------------------------")
pfw_search = pfw_search_applications_minimal(
    query=f'patentNumber:{patent_number}',
    fields=['applicationNumberText', 'examinerNameText', 'groupArtUnitNumber'],
    limit=1
)

if pfw_search['applications']:
    app_number = pfw_search['applications'][0]['applicationNumberText']
    examiner = pfw_search['applications'][0].get('examinerNameText', 'N/A')
    art_unit = pfw_search['applications'][0].get('groupArtUnitNumber', 'N/A')

    print(f"Application: {app_number}")
    print(f"Examiner: {examiner}")
    print(f"Art Unit: {art_unit}")

    # Get key prosecution documents
    noa_docs = pfw_get_application_documents(
        app_number=app_number,
        document_code='NOA',
        limit=5
    )

    rejection_docs = pfw_get_application_documents(
        app_number=app_number,
        document_code='CTFR',
        limit=10
    )

    print(f"Notice of Allowances: {noa_docs['count']}")
    print(f"Office Action Rejections: {rejection_docs['count']}")

# PHASE 3: Petition Analysis (FPD)
print(f"\nPHASE 3: PETITION HISTORY (FPD)")
print(f"-------------------------------")
petitions = fpd_search_petitions_minimal(
    application_number=app_number,
    limit=10
)

petition_count = petitions.get('recordTotalQuantity', 0)
print(f"Total petitions: {petition_count}")

if petition_count > 0:
    print(f"⚠️ Petition(s) filed during prosecution")
else:
    print(f"✅ No petitions - normal prosecution")

# PHASE 4: PTAB Challenges
print(f"\nPHASE 4: PTAB CHALLENGES")
print(f"------------------------")
ptab_proceedings = ptab_search_proceedings_balanced(
    patent_number=patent_number,
    limit=10
)

ptab_count = ptab_proceedings.get('recordTotalQuantity', 0)
print(f"PTAB proceedings: {ptab_count}")

if ptab_count > 0:
    print(f"⚠️ Patent has been challenged at PTAB")
else:
    print(f"✅ No PTAB challenges")

# COMPREHENSIVE ASSESSMENT
print(f"\n" + "="*50)
print(f"COMPREHENSIVE RISK ASSESSMENT")
print(f"="*50)

# Risk scoring
risk_score = 0
risk_factors = []

if len(examiner_citations) < 5:
    risk_score += 2
    risk_factors.append("Low examiner citation count")

if category_dist.get('NPL', 0) == 0:
    risk_score += 2
    risk_factors.append("No NPL citations")

if petition_count > 0:
    risk_score += 3
    risk_factors.append(f"{petition_count} petition(s) filed")

if ptab_count > 0:
    risk_score += 3
    risk_factors.append(f"{ptab_count} PTAB proceeding(s)")

risk_level = "HIGH" if risk_score >= 6 else "MEDIUM" if risk_score >= 3 else "LOW"

print(f"\nRisk Level: {risk_level} (Score: {risk_score}/10)")
if risk_factors:
    print(f"Risk Factors:")
    for factor in risk_factors:
        print(f"  - {factor}")
else:
    print(f"✅ Strong patent with no significant risk factors")
```

**Token Efficiency for Complete Workflow:**

**Without Optimization:**
- Citations: 100 results × 18 fields = ~200KB
- PFW: 50 docs × full metadata = ~500KB
- FPD: 10 petitions × full metadata = ~100KB
- PTAB: 10 proceedings × full metadata = ~200KB
- **Total: ~1MB**

**With Ultra-Minimal Optimization:**
- Citations: 100 results × 3 fields = ~30KB
- PFW: 50 docs × 3 fields = ~10KB
- FPD: 10 petitions × 3 fields = ~10KB
- PTAB: 10 proceedings × 3 fields = ~20KB
- **Total: ~70KB (93% reduction)**

---

## Known Patents for Testing

These patents/applications can be used for testing citation workflows:

**For Cross-MCP Integration Testing:**
- **Patent 9049188** (Application 14171705) - Has IPR proceeding IPR2025-00562
- **Application 18823722** - For citation analysis testing (Examiner: MEKHLIN, ELI S, Art Unit 1759)
- **Patent 7971071** (Application 11752072) - Inventors: Wilbur J. Walkoe, John Walkoe

**For Examiner Analysis Testing (via PFW):**
- Search for examiner "SMITH" in various art units
- Search for art unit 2854, 1759, 2128, 3600

**For Technology Landscape Testing:**
- Technology Center 2100 (Computer Architecture/Software)
- Technology Center 2800 (Semiconductors/Electrical)
- Technology Center 1600 (Biotechnology/Organic Chemistry)

---

## Full Tool Reference

### Search Tools (Progressive Disclosure)

**search_citations_minimal** - Citation Discovery (90-95% context reduction)
- **Purpose**: Fast citation discovery with essential fields
- **Fields**: 8 preset fields (citedDocumentIdentifier, patentApplicationNumber, publicationNumber, citationCategoryCode, examinerCitedReferenceIndicator, groupArtUnitNumber, techCenter, officeActionDate)
- **Ultra-Minimal Mode**: Custom `fields` parameter for 99% reduction (2-3 fields only)
- **Recommended**: 50-100 results for discovery workflow
- **Date Range**: officeActionDate from 2017-10-01 to 30 days ago

**search_citations_balanced** - Detailed Citation Analysis (70-80% context reduction)
- **Purpose**: Comprehensive citation analysis with full context
- **Fields**: 18+ fields including all minimal fields plus relatedClaimNumberText, passageLocationText, officeActionCategory, workGroupNumber, and more
- **Ultra-Minimal Mode**: Custom `fields` parameter for 99% reduction
- **Recommended**: 10-20 results for analysis workflow
- **Date Range**: officeActionDate from 2017-10-01 to 30 days ago

### Detail Tools

**get_citation_details** - Full Citation Record
- **Purpose**: Complete citation details with optional citing context
- **Use Cases**: Specific citation analysis, passage examination, full record retrieval
- **⚠️ Returns**: Citation METADATA only, NOT actual documents (use PFW for documents)

**get_available_fields** - Field Discovery
- **Purpose**: Discover searchable field names and query syntax
- **Use Cases**: Query construction, field validation, syntax learning

**validate_query** - Query Optimization
- **Purpose**: Validate Solr/Lucene syntax and get optimization suggestions
- **Use Cases**: Query debugging, performance optimization, syntax learning

**get_citation_statistics** - Statistical Analysis
- **Purpose**: Get database statistics and aggregations
- **Use Cases**: Volume analysis, trend identification, strategic planning

### Guidance Tool

**citations_get_guidance** - Selective Workflow Guidance
- **Purpose**: Context-efficient selective guidance sections
- **Sections**: overview, workflows_pfw, workflows_ptab, workflows_fpd, workflows_complete, citation_codes, data_coverage, fields, tools, errors, cost
- **Efficiency**: 1-12KB per section vs 62KB full content (90-95% reduction)

---

## Query Syntax

### Basic Search Operators

```python
# Exact match
criteria='publicationNumber:9049188'

# Wildcard search
criteria='patentApplicationNumber:17896*'

# Field-specific search
criteria='groupArtUnitNumber:2854'

# Date range (CRITICAL: 2017-10-01+ only)
criteria='officeActionDate:[2017-10-01 TO *]'
criteria='officeActionDate:[2020-01-01 TO 2024-12-31]'

# Boolean operators
criteria='techCenter:2100 AND citationCategoryCode:NPL'
criteria='groupArtUnitNumber:2854 OR groupArtUnitNumber:1759'
criteria='citationCategoryCode:X AND examinerCitedReferenceIndicator:true'
```

### Common Search Patterns

```python
# Find all citations for a patent
criteria='publicationNumber:9049188 AND officeActionDate:[2017-10-01 TO *]'

# Find citations for an application
criteria='patentApplicationNumber:17896175 AND officeActionDate:[2017-10-01 TO *]'

# Find examiner citations only
criteria='examinerCitedReferenceIndicator:true AND groupArtUnitNumber:2854'

# Find NPL citations
criteria='citationCategoryCode:NPL AND techCenter:2100'

# Find citations in art unit with date range
criteria='groupArtUnitNumber:2854 AND officeActionDate:[2020-01-01 TO 2024-12-31]'

# Find X/Y category citations (critical prior art)
criteria='(citationCategoryCode:X OR citationCategoryCode:Y) AND publicationNumber:9049188'
```

### Important Date Coverage Notes

**⚠️ CRITICAL**: Citation API coverage is **October 1, 2017 to 30 days prior** to current date.

**Always include date filter:**
```python
criteria='yourQuery AND officeActionDate:[2017-10-01 TO *]'
```

**For application-based searches, use filing date 2015+:**
```python
# When searching via PFW for examiner applications
pfw_search_applications_minimal(
    query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
    # 2015 start date accounts for 1-2 year lag to first office action
)
```

---

## Performance Tips

### Progressive Disclosure Strategy

1. **Discovery (Minimal)**: Use `search_citations_minimal` for initial exploration (50-100 results)
2. **Selection**: User/AI reviews results and selects 10-20 citations of interest
3. **Analysis (Balanced)**: Use `search_citations_balanced` for selected citations (10-20 results)
4. **Details**: Use `get_citation_details` for 1-5 specific citations (full data)

**Token Savings**: This progressive approach reduces context by ~93% compared to fetching full data upfront.

### Best Practices

- **Always filter by date**: Include `officeActionDate:[2017-10-01 TO *]` in queries
- **Start with minimal search** for discovery (50-100 results)
- **Use ultra-minimal mode** for high-volume extraction (custom `fields` parameter)
- **Limit result sets**: 20-50 results for balanced searches
- **Leverage cross-MCP integration** for complete intelligence
- **Use PFW for documents**: Citation API returns metadata only, use PFW for office action documents

### Token Efficiency Comparison

```
Scenario: Search 100 citations for portfolio analysis

Ultra-minimal mode (2 fields):
  ~80 chars/result × 100 = ~8KB total (99% reduction)

Preset minimal (8 fields):
  ~400 chars/result × 100 = ~40KB total (95% reduction)

Preset balanced (18 fields):
  ~2,000 chars/result × 100 = ~200KB total (80% reduction)

Full data (NEVER):
  ~10,000 chars/result × 100 = ~1MB total (unusable)
```

---

## Integration Patterns

### With Patent File Wrapper (PFW) MCP

**Shared Fields:**
- `patentApplicationNumber` ↔ `applicationNumberText` - Primary linking key
- `publicationNumber` ↔ `patentNumber` - For granted patents
- `groupArtUnitNumber` - Art unit correlation

**Common Workflows:**
- **Examiner Analysis**: PFW (get apps) → Citations (analyze patterns)
- **Document Retrieval**: Citations (get metadata) → PFW (get office action PDFs)
- **Citation Context**: Citations (find references) → PFW (extract examiner reasoning)

### With PTAB MCP

**Shared Fields:**
- `publicationNumber` ↔ `patentNumber` - Primary linking key
- `groupArtUnitNumber` - Art unit correlation

**Common Workflows:**
- **Prior Art Validation**: Citations (prosecution) → PTAB (compare IPR prior art)
- **Vulnerability Assessment**: Citations (patterns) → PTAB (challenge risk)
- **IPR Research**: PTAB (proceedings) → Citations (prosecution analysis)

### With FPD MCP

**Shared Fields:**
- `patentApplicationNumber` ↔ `applicationNumber` - Primary linking key
- `groupArtUnitNumber` - Art unit correlation

**Common Workflows:**
- **Petition Correlation**: FPD (petitions) → Citations (quality assessment)
- **Art Unit Quality**: Citations (density) → FPD (petition rate)
- **Prosecution Quality**: Citations (examiner search) → FPD (petition red flags)

---

## Questions?

For more detailed workflow guidance, use the `citations_get_guidance` tool with specific sections like "workflows_pfw", "workflows_ptab", or "workflows_complete" for targeted LLM-friendly guidance for complex multi-step analyses.
