"""Technology Citation Landscape Prompt

Map prior art citation landscape for technology areas using art unit and tech center analysis
with PFW integration
"""

from . import mcp


@mcp.prompt(
    name="technology_citation_landscape_PFW",
    description="Map prior art citation landscape for technology areas. At least ONE required (technology_keywords, tech_center, or art_unit). date_start: YYYY-MM-DD for filing date range. Requires PFW MCP.",
)
async def technology_citation_landscape_PFW_prompt(
    technology_keywords: str = "",
    tech_center: str = "",
    art_unit: str = "",
    date_start: str = "2015-01-01",
) -> str:
    """Map citation landscape for technology areas to identify prior art patterns and examiner citation preferences.

    Args:
        technology_keywords: Technology terms for search (e.g., 'machine learning', 'wireless communication')
        tech_center: Technology center number (e.g., '2100', '3600')
        art_unit: Specific art unit number (e.g., '2854')
        date_start: Start date for analysis (default: 2015-01-01, accounts for filing-to-OA lag)
    """

    if not technology_keywords and not tech_center and not art_unit:
        return """
# TECHNOLOGY CITATION LANDSCAPE MAPPING

❌ **ERROR: Missing Search Parameters**

Please provide at least one search parameter:
- **Technology Keywords**: Technical terms (e.g., 'artificial intelligence', 'blockchain')
- **Tech Center**: Technology center number (e.g., '2100', '3600')
- **Art Unit**: Specific art unit (e.g., '2854')

**Example Usage:**
```
technology_keywords='machine learning'
tech_center='2100'
art_unit='2854'
```
"""

    return f"""
# TECHNOLOGY CITATION LANDSCAPE MAPPING

**Technology Focus:**
- **Keywords**: {technology_keywords or "Not specified"}
- **Tech Center**: {tech_center or "Not specified"}
- **Art Unit**: {art_unit or "Not specified"}
- **Date Range**: {date_start} to present
**Context:** Filing dates from {date_start} → Office actions from 2017-10-01+ (API availability)

## Step 1: Discovery Search (Ultra-Minimal Mode)

```python
# Build search criteria for technology area
criteria_parts = []
if "{technology_keywords}":
    criteria_parts.append(f'citedDocumentTitle:"{technology_keywords}"')
if "{tech_center}":
    criteria_parts.append(f'techCenter:{tech_center}')
if "{art_unit}":
    criteria_parts.append(f'groupArtUnitNumber:{art_unit}')

# Add date constraint (CRITICAL: Citations only from 2017-10-01+, but use filing date context)
criteria_parts.append('officeActionDate:[2017-10-01 TO *]')

criteria = ' AND '.join(criteria_parts)

# Ultra-minimal discovery (99% token reduction)
landscape_citations = search_citations_minimal(
    criteria=criteria,
    fields=['citationCategoryCode', 'groupArtUnitNumber', 'techCenter', 'citedDocumentIdentifier'],
    rows=100
)
```

## Step 2: Analyze Citation Patterns

```python
from collections import Counter

# Analyze citation categories
category_dist = Counter()
art_unit_dist = Counter()

for citation in landscape_citations['response']['docs']:
    category_dist[citation.get('citationCategoryCode', 'Unknown')] += 1
    art_unit_dist[citation.get('groupArtUnitNumber', 'Unknown')] += 1

print("Citation Category Distribution:")
for cat, count in category_dist.items():
    print(f"  - {{cat}}: {{count}}")

print("\\nArt Unit Distribution:")
for unit, count in art_unit_dist.most_common(10):
    print(f"  - Art Unit {{unit}}: {{count}} citations")
```

## Step 3: Cross-Reference with PFW (Patent Applications)

```python
# Get top art units for deeper analysis
top_art_units = [unit for unit, count in art_unit_dist.most_common(3)]

for art_unit in top_art_units:
    # Search applications in this art unit + technology
    tech_filter = f' AND inventionTitle:"{technology_keywords}"' if "{technology_keywords}" else ''

    pfw_apps = pfw_search_applications_minimal(
        query=f'groupArtUnitNumber:{{art_unit}}*{{tech_filter}} AND filingDate:[{date_start} TO *]',
        fields=['applicationNumberText', 'applicationMetaData.inventionTitle', 'applicationMetaData.groupArtUnitNumber'],
        limit=20
    )

    print(f"\\nArt Unit {{art_unit}} Applications:")
    for app in pfw_apps['applications'][:5]:
        print(f"  - {{app['applicationNumberText']}}: {{app['applicationMetaData']['inventionTitle'][:80]}}")
```

## Step 4: Prior Art Reference Analysis

```python
# Get balanced citation data for detailed analysis
detailed_citations = search_citations_balanced(
    criteria=criteria,
    rows=50
)

# Analyze frequently cited references
cited_refs = Counter()
for citation in detailed_citations['response']['docs']:
    ref_id = citation.get('citedDocumentIdentifier', 'Unknown')
    cited_refs[ref_id] += 1

print("\\nMost Frequently Cited References:")
for ref, count in cited_refs.most_common(10):
    print(f"  - {{ref}}: cited {{count}} times")
```

## Expected Technology Landscape Intelligence

1. **Citation Category Preferences** - X (US), Y (foreign), NPL distribution by technology
2. **Art Unit Hotspots** - Which art units cite most in this technology area
3. **Prior Art Patterns** - Most frequently cited references and patent families
4. **Technology Evolution** - Citation trends over time periods
5. **Cross-MCP Integration** - Applications and prosecution patterns in this technology

**Token Efficiency:** 4 custom fields × 100 results = ~20KB (vs ~400KB with all fields)
"""
