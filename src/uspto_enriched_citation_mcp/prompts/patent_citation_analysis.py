"""Patent Citation Analysis Prompt

Complete citation analysis for specific patent or application with prosecution context
"""

from . import mcp


@mcp.prompt(
    name="patent_citation_analysis",
    description="Complete citation analysis for specific patent or application. At least ONE required (patent_number or application_number). include_context: true/false for prosecution context from PFW.",
)
async def patent_citation_analysis_prompt(
    patent_number: str = "", application_number: str = "", include_context: str = "true"
) -> str:
    """Analyze all citations for a specific patent or application with optional prosecution context.

    Args:
        patent_number: Patent number (e.g., '9049188')
        application_number: Application number (e.g., '14171705')
        include_context: Include prosecution context from PFW ('true'/'false')
    """

    if not patent_number and not application_number:
        return """
# PATENT CITATION ANALYSIS

❌ **ERROR: Missing Identifier**

Please provide either:
- **Patent Number**: Granted patent number (e.g., '9049188')
- **Application Number**: Application number (e.g., '14171705')

**Example Usage:**
```
patent_number='9049188'
application_number='14171705'
include_context='true'
```
"""

    identifier = patent_number or application_number
    id_type = "patent" if patent_number else "application"

    return f"""
# PATENT CITATION ANALYSIS

**Target {id_type.title()}:** {identifier}
**Include Prosecution Context:** {include_context}

## Step 1: Get Citation Records

```python
# Search by patent or application number
if "{patent_number}":
    criteria = f'publicationNumber:{patent_number}'
else:
    criteria = f'patentApplicationNumber:{application_number}'

# Add date constraint
criteria += ' AND officeActionDate:[2017-10-01 TO *]'

# Get comprehensive citation data
citations = search_citations_balanced(
    criteria=criteria,
    rows=100
)

print(f"Found {{citations['response']['numFound']}} citation records")
```

## Step 2: Citation Analysis

```python
from collections import Counter

# Categorize citations
categories = Counter()
sources = Counter()
art_units = Counter()

for citation in citations['response']['docs']:
    categories[citation.get('citationCategoryCode', 'Unknown')] += 1

    if citation.get('examinerCitedReferenceIndicator') == 'true':
        sources['Examiner'] += 1
    else:
        sources['Applicant'] += 1

    art_units[citation.get('groupArtUnitNumber', 'Unknown')] += 1

print("Citation Summary:")
print(f"Categories: {{dict(categories)}}")
print(f"Sources: {{dict(sources)}}")
print(f"Art Units: {{dict(art_units)}}")
```

## Step 3: Detailed Citation Review

```python
# Get individual citation details for key references
key_citations = citations['response']['docs'][:10]  # Top 10

for i, citation in enumerate(key_citations):
    citation_id = citation.get('citationIdentifier')
    if citation_id:
        details = get_citation_details(
            citation_id=citation_id,
            include_context=True
        )

        print(f"\\nCitation {{i+1}}:")
        print(f"  Reference: {{citation.get('citedDocumentIdentifier')}}")
        print(f"  Category: {{citation.get('citationCategoryCode')}}")
        print(f"  Source: {{'Examiner' if citation.get('examinerCitedReferenceIndicator') == 'true' else 'Applicant'}}")

        if details.get('citingPassageText'):
            print(f"  Context: {{details['citingPassageText'][:200]}}...")
```

## Step 4: Prosecution Context (if enabled)

```python
if "{include_context}".lower() == 'true':
    # Get prosecution history from PFW
    if "{application_number}":
        app_num = "{application_number}"
    else:
        # Need to find application number from patent number
        print("Note: Need application number for prosecution context")
        app_num = None

    if app_num:
        # Get prosecution documents
        docs = pfw_get_application_documents(
            app_number=app_num,
            document_code='NOA',  # Notice of Allowance
            limit=5
        )

        print(f"\\nProsecution Context:")
        print(f"Found {{docs['count']}} Notice of Allowance documents")

        # Get examiner's reasoning from NOA
        if docs['documentBag']:
            noa_doc = docs['documentBag'][0]
            noa_content = pfw_get_document_content(
                app_number=app_num,
                document_identifier=noa_doc['documentIdentifier']
            )

            print("Examiner's allowance reasoning available for comparison with citation decisions")
```

## Expected Analysis Results

1. **Citation Summary** - Total citations by category, source, and art unit
2. **Key References** - Most important cited documents with context
3. **Citation Context** - Examiner's reasoning for citing specific references
4. **Prosecution Correlation** - How citations influenced prosecution decisions
5. **Strategic Intelligence** - Citation patterns for similar cases

**Cross-MCP Integration:** Links citation decisions to prosecution outcomes for strategic insights.
"""
