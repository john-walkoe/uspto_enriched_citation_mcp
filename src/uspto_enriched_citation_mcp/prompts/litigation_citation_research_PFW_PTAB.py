"""Litigation Citation Research Prompt

Complete litigation citation research package using PFW, Citations, and PTAB cross-MCP integration
for comprehensive case preparation
"""

from . import mcp


@mcp.prompt(
    name="litigation_citation_research_PFW_PTAB",
    description="Complete litigation citation research package. At least ONE required (patent_number or application_number). include_ptab: true/false for PTAB analysis. Requires PFW MCP, optional PTAB MCP.",
)
async def litigation_citation_research_PFW_PTAB_prompt(
    patent_number: str = "",
    application_number: str = "",
    include_ptab: str = "true",
) -> str:
    """Comprehensive litigation research combining citation analysis, prosecution history, and PTAB proceedings.

    Args:
        patent_number: Patent number for litigation research (e.g., '9049188')
        application_number: Application number if patent number not available
        include_ptab: Include PTAB proceedings analysis ('true'/'false')
    """

    if not patent_number and not application_number:
        return """
# LITIGATION CITATION RESEARCH PACKAGE

❌ **ERROR: Missing Patent Identifier**

Please provide either:
- **Patent Number**: Target patent for litigation (e.g., '9049188')
- **Application Number**: Application number if patent number unknown

**Example Usage:**
```
patent_number='9049188'
include_ptab='true'
```
"""

    identifier = patent_number or application_number
    id_type = "patent" if patent_number else "application"

    return f"""
# LITIGATION CITATION RESEARCH PACKAGE

**Target {id_type.title()}:** {identifier}
**Include PTAB Analysis:** {include_ptab}

## Phase 1: Citation Intelligence (Enriched Citation MCP)

### Step 1.1: Get All Citation Records

```python
# Search for all citations related to the patent/application
if "{patent_number}":
    criteria = f'publicationNumber:{patent_number}'
else:
    criteria = f'patentApplicationNumber:{application_number}'

# Include date constraint (citations from 2017-10-01+ only)
criteria += ' AND officeActionDate:[2017-10-01 TO *]'

# Get comprehensive citation data
citations = search_citations_balanced(
    criteria=criteria,
    rows=200
)

print(f"CITATION INTELLIGENCE")
print(f"Found {{citations['response']['numFound']}} citation records")
```

### Step 1.2: Citation Analysis for Litigation

```python
from collections import Counter

# Categorize for litigation strategy
examiner_citations = []
applicant_citations = []
key_prior_art = Counter()

for citation in citations['response']['docs']:
    ref_id = citation.get('citedDocumentIdentifier', 'Unknown')
    category = citation.get('citationCategoryCode', 'Unknown')

    # Track cited references for invalidity research
    key_prior_art[ref_id] += 1

    # Separate examiner vs applicant citations
    if citation.get('examinerCitedReferenceIndicator') == 'true':
        examiner_citations.append(citation)
    else:
        applicant_citations.append(citation)

print(f"Examiner citations: {{len(examiner_citations)}}")
print(f"Applicant citations: {{len(applicant_citations)}}")

print("\\nMost frequently cited references (invalidity targets):")
for ref, count in key_prior_art.most_common(10):
    print(f"  - {{ref}}: cited {{count}} times")
```

### Step 1.3: Detailed Citation Context

```python
# Get context for top citations
top_citations = citations['response']['docs'][:10]

litigation_citations = []
for citation in top_citations:
    citation_id = citation.get('citationIdentifier')
    if citation_id:
        details = get_citation_details(
            citation_id=citation_id,
            include_context=True
        )

        litigation_citations.append({{
            'reference': citation.get('citedDocumentIdentifier'),
            'category': citation.get('citationCategoryCode'),
            'source': 'Examiner' if citation.get('examinerCitedReferenceIndicator') == 'true' else 'Applicant',
            'context': details.get('citingPassageText', 'No context available')[:300]
        }})

print("\\nKey Citations with Context:")
for i, cite in enumerate(litigation_citations):
    print(f"{{i+1}}. {{cite['reference']}} ({{cite['category']}}, {{cite['source']}})")
    print(f"   Context: {{cite['context']}}")
```

## Phase 2: Prosecution History (PFW MCP)

### Step 2.1: Get Complete Prosecution History

```python
# Get application number if we only have patent number
if "{patent_number}" and not "{application_number}":
    # Search for application using patent number
    pfw_search = pfw_search_applications_minimal(
        query=f'patentNumber:{patent_number}',
        fields=['applicationNumberText'],
        limit=1
    )
    app_number = pfw_search['applications'][0]['applicationNumberText'] if pfw_search['applications'] else None
else:
    app_number = "{application_number}"

if app_number:
    print(f"\\nPROSECUTION HISTORY ANALYSIS")
    print(f"Application Number: {{app_number}}")

    # Get key prosecution documents
    key_docs = pfw_get_application_documents(
        app_number=app_number,
        limit=50
    )

    print(f"Found {{key_docs['count']}} prosecution documents")
```

### Step 2.2: Extract Critical Prosecution Evidence

```python
# Get specific document types for litigation
noa_docs = pfw_get_application_documents(
    app_number=app_number,
    document_code='NOA',  # Notice of Allowance
    limit=10
)

rejection_docs = pfw_get_application_documents(
    app_number=app_number,
    document_code='CTFR',  # Final Rejection
    limit=10
)

print(f"Notice of Allowance documents: {{noa_docs['count']}}")
print(f"Final Rejection documents: {{rejection_docs['count']}}")

# Extract examiner's final reasoning
if noa_docs['documentBag']:
    noa_content = pfw_get_document_content(
        app_number=app_number,
        document_identifier=noa_docs['documentBag'][0]['documentIdentifier']
    )
    print("\\nExaminer's allowance reasoning extracted for claim construction evidence")
```

## Phase 3: PTAB Proceedings (if enabled)

```python
if "{include_ptab}".lower() == 'true' and "{patent_number}":
    print(f"\\nPTAB PROCEEDINGS ANALYSIS")

    # Search for PTAB proceedings involving this patent
    ptab_proceedings = ptab_search_proceedings_balanced(
        patent_number="{patent_number}",
        limit=20
    )

    print(f"Found {{ptab_proceedings.get('response', {{}}).get('numFound', 0)}} PTAB proceedings")

    if ptab_proceedings.get('response', {{}}).get('docs'):
        print("\\nPTAB Proceeding Types:")
        proceeding_types = Counter()

        for proceeding in ptab_proceedings['response']['docs']:
            proc_type = proceeding.get('proceedingTypeCategory', 'Unknown')
            proceeding_types[proc_type] += 1

        for proc_type, count in proceeding_types.items():
            print(f"  - {{proc_type}}: {{count}}")

        # Get decisions for key proceedings
        key_proceeding = ptab_proceedings['response']['docs'][0]
        proceeding_number = key_proceeding.get('proceedingNumber')

        if proceeding_number:
            decisions = ptab_search_decisions_balanced(
                proceeding_number=proceeding_number,
                limit=10
            )

            print(f"\\nFound {{decisions.get('response', {{}}).get('numFound', 0)}} decisions for proceeding {{proceeding_number}}")
```

## Phase 4: Comprehensive Litigation Package

```python
print(f"\\n" + "="*50)
print(f"LITIGATION RESEARCH SUMMARY")
print(f"="*50)

# Citation intelligence summary
print(f"\\n1. CITATION INTELLIGENCE:")
print(f"   - Total citations: {{citations['response']['numFound']}}")
print(f"   - Examiner citations: {{len(examiner_citations)}}")
print(f"   - Key prior art references: {{len(key_prior_art)}}")

# Prosecution history summary
print(f"\\n2. PROSECUTION HISTORY:")
print(f"   - Application: {{app_number or 'Not found'}}")
print(f"   - Total documents: {{key_docs['count'] if 'key_docs' in locals() else 'N/A'}}")
print(f"   - Allowance documents: {{noa_docs['count'] if 'noa_docs' in locals() else 'N/A'}}")

# PTAB summary
if "{include_ptab}".lower() == 'true':
    ptab_count = ptab_proceedings.get('response', {{}}).get('numFound', 0) if 'ptab_proceedings' in locals() else 0
    print(f"\\n3. PTAB PROCEEDINGS:")
    print(f"   - Total proceedings: {{ptab_count}}")
    print(f"   - Proceeding types: {{dict(proceeding_types) if 'proceeding_types' in locals() else 'None'}}")

print(f"\\n4. LITIGATION READINESS:")
print(f"   - Citation context extracted: {{len(litigation_citations)}} key references")
print(f"   - Prosecution reasoning available: {{'Yes' if 'noa_content' in locals() else 'No'}}")
print(f"   - PTAB challenge history: {{'Yes' if ptab_count > 0 else 'No'}}")
```

## Expected Litigation Intelligence

1. **Invalidity Analysis** - Comprehensive prior art cited during prosecution
2. **Claim Construction** - Examiner's interpretation from prosecution history
3. **Prosecution Estoppel** - Amendments and arguments that may limit claim scope
4. **PTAB Vulnerability** - Existing or potential post-grant challenges
5. **Strategic Evidence** - Key documents and examiner reasoning for litigation strategy

**Cross-MCP Integration Benefits:**
- **Citation + PFW**: Links prior art to prosecution strategy and claim amendments
- **Citation + PTAB**: Identifies prior art used in post-grant challenges
- **PFW + PTAB**: Connects prosecution history to board proceeding outcomes
- **All Three**: Complete litigation intelligence from filing through post-grant

**Data Coverage:** Citation data from 2017-10-01+ (API limitation), PTAB proceedings from 2012+, complete PFW prosecution history.

**Token Efficiency:** Progressive disclosure from ultra-minimal discovery to balanced analysis for critical documents.
"""
