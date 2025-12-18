"""Art Unit Citation Assessment Prompt

Analyze art unit citation norms and examiner patterns for prosecution strategy
and art unit quality assessment
"""

from . import mcp


@mcp.prompt(
    name="art_unit_citation_assessment",
    description="Analyze art unit citation norms and examiner patterns. art_unit* (required). date_start: YYYY-MM-DD for analysis period (default: 2015-01-01).",
)
async def art_unit_citation_assessment_prompt(
    art_unit: str = "", date_start: str = "2015-01-01"
) -> str:
    """Analyze citation patterns within specific art units to understand examiner norms and prosecution expectations.

    Args:
        art_unit: Art unit number (e.g., '2854', '1759')
        date_start: Start date for analysis (default: 2015-01-01, accounts for filing-to-OA lag)
    """

    if not art_unit:
        return """
# ART UNIT CITATION ASSESSMENT

❌ **ERROR: Missing Art Unit**

Please provide an art unit number:
- **Art Unit**: Specific art unit (e.g., '2854', '1759', '3700')

**Example Usage:**
```
art_unit='2854'
date_start='2015-01-01'
```
"""

    return f"""
# ART UNIT CITATION ASSESSMENT

**Target Art Unit:** {art_unit}
**Analysis Period:** {date_start} to present
**Context:** Filing dates from {date_start} → Office actions from 2017-10-01+ (API availability)

## Step 1: Art Unit Citation Overview (Ultra-Minimal)

```python
# Get citation patterns for this art unit
# Note: Use 2015-01-01 filing context but citations only available from 2017-10-01+
citations = search_citations_minimal(
    criteria=f'groupArtUnitNumber:{art_unit} AND officeActionDate:[2017-10-01 TO *]',
    fields=['examinerCitedReferenceIndicator', 'citationCategoryCode', 'patentApplicationNumber'],
    rows=200
)

print(f"Art Unit {art_unit} Citation Analysis:")
print(f"Total citations analyzed: {{citations['response']['numFound']}}")
```

## Step 2: Citation Source Analysis

```python
from collections import Counter

# Analyze citation sources and categories
source_analysis = Counter()
category_analysis = Counter()
apps_with_citations = set()

for citation in citations['response']['docs']:
    # Track examiner vs applicant citations
    if citation.get('examinerCitedReferenceIndicator') == 'true':
        source_analysis['Examiner Citations'] += 1
    else:
        source_analysis['Applicant Citations'] += 1

    # Track citation categories
    category_analysis[citation.get('citationCategoryCode', 'Unknown')] += 1

    # Track unique applications
    apps_with_citations.add(citation.get('patentApplicationNumber'))

print("\\nCitation Source Distribution:")
for source, count in source_analysis.items():
    percentage = (count / citations['response']['numFound']) * 100
    print(f"  - {{source}}: {{count}} ({{percentage:.1f}}%)")

print("\\nCitation Category Distribution:")
for category, count in category_analysis.items():
    percentage = (count / citations['response']['numFound']) * 100
    print(f"  - {{category}}: {{count}} ({{percentage:.1f}}%)")

print(f"\\nUnique Applications with Citations: {{len(apps_with_citations)}}")
```

## Step 3: Cross-Reference with PFW Applications

```python
# Get applications filed in this art unit (account for filing-to-OA lag)
pfw_apps = pfw_search_applications_minimal(
    query=f'groupArtUnitNumber:{art_unit}* AND filingDate:[{date_start} TO *]',
    fields=['applicationNumberText', 'applicationMetaData.examinerNameText', 'applicationMetaData.groupArtUnitNumber'],
    limit=100
)

print(f"\\nPFW Applications in Art Unit {art_unit}:")
print(f"Total applications found: {{len(pfw_apps['applications'])}}")

# Calculate citation density
if len(pfw_apps['applications']) > 0:
    citation_density = len(apps_with_citations) / len(pfw_apps['applications'])
    print(f"Citation density: {{citation_density:.2f}} (applications with citations / total applications)")
```

## Step 4: Examiner-Level Analysis

```python
# Group by examiner within the art unit
examiner_stats = {{}}

for app in pfw_apps['applications']:
    examiner = app['applicationMetaData'].get('examinerNameText', 'Unknown')
    app_number = app['applicationNumberText']

    if examiner not in examiner_stats:
        examiner_stats[examiner] = {{'apps': 0, 'cited_apps': 0}}

    examiner_stats[examiner]['apps'] += 1

    # Check if this application has citations
    if app_number in apps_with_citations:
        examiner_stats[examiner]['cited_apps'] += 1

print("\\nExaminer Citation Patterns:")
for examiner, stats in examiner_stats.items():
    if stats['apps'] >= 3:  # Only show examiners with 3+ apps
        cite_rate = (stats['cited_apps'] / stats['apps']) * 100 if stats['apps'] > 0 else 0
        print(f"  - {{examiner}}: {{stats['cited_apps']}}/{{stats['apps']}} apps ({{cite_rate:.1f}}% citation rate)")
```

## Step 5: Art Unit Benchmarking

```python
# Get detailed citation data for comparison
detailed_citations = search_citations_balanced(
    criteria=f'groupArtUnitNumber:{art_unit} AND officeActionDate:[2017-10-01 TO *]',
    rows=100
)

# Calculate art unit metrics
total_citations = detailed_citations['response']['numFound']
avg_citations_per_app = total_citations / len(apps_with_citations) if apps_with_citations else 0

print(f"\\nArt Unit {art_unit} Metrics:")
print(f"Average citations per application: {{avg_citations_per_app:.1f}}")

# Compare citation categories to USPTO averages (approximate benchmarks)
x_citations = category_analysis.get('X', 0)  # US Patents
y_citations = category_analysis.get('Y', 0)  # Foreign Patents
npl_citations = category_analysis.get('NPL', 0)  # Non-Patent Literature

if total_citations > 0:
    print(f"Citation mix:")
    print(f"  - US Patents (X): {{x_citations}} ({{(x_citations/total_citations)*100:.1f}}%)")
    print(f"  - Foreign Patents (Y): {{y_citations}} ({{(y_citations/total_citations)*100:.1f}}%)")
    print(f"  - Non-Patent Literature (NPL): {{npl_citations}} ({{(npl_citations/total_citations)*100:.1f}}%)")
```

## Expected Art Unit Intelligence

1. **Citation Density** - How frequently applications in this art unit receive citations
2. **Source Patterns** - Examiner vs applicant citation ratios (examiner initiative vs applicant submissions)
3. **Category Preferences** - US vs foreign vs non-patent literature citation patterns
4. **Examiner Variation** - Citation behavior differences among examiners in the art unit
5. **Prosecution Norms** - Expected citation volume and patterns for new applications

## Strategic Applications

- **Prosecution Planning** - Set realistic expectations for citation volume and sources
- **Examiner Selection** - Understand citation patterns when specific examiner assignment matters
- **Prior Art Strategy** - Align applicant citation submissions with art unit norms
- **Quality Assessment** - Compare art unit citation thoroughness across technology areas

**Date Context Note:** Analysis covers applications filed from {date_start} forward, with citation data available from 2017-10-01+ due to API limitations. This accounts for the typical 1-2 year lag between filing and first office action.

**Token Efficiency:** 3-4 custom fields for discovery, escalating to balanced mode for detailed analysis.
"""
