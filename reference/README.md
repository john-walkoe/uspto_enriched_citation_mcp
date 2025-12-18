# USPTO Citations MCP Reference Documentation

This directory contains official USPTO reference documentation used by the Enriched Citation MCP.

## Files

### `USPTO Enriched Citation API v3.md`
**Source:** [USPTO Developer Portal - Enriched Citation API v3](https://developer.uspto.gov/api-catalog/uspto-enriched-citation-api-v3)
**Updated:** July 11, 2024
**Size:** ~27 KB

Official USPTO documentation for the Enriched Citation API v3, including API syntax and Lucene Query Parser reference.

**Contents:**
- **API Overview**: AI-powered citation extraction from office actions (Oct 2017+)
- **Machine Learning Details**: NLP and entity extraction algorithms for citation analysis
- **API Endpoints**:
  - `/enriched_cited_reference_metadata/v3/fields` - Discover searchable field names
  - `/enriched_cited_reference_metadata/v3/records` - Search citation records
- **Lucene Query Syntax**: Complete Apache Lucene Query Parser Syntax reference
- **API Capabilities**: Solr/Lucene based search with full boolean operators, wildcards, ranges

**Key API Information:**
- **Date Coverage**: Office actions mailed from October 1, 2017 to 30 days prior to current date
- **Search Engine**: Solr/Lucene indexing with full query syntax support
- **AI/ML Extraction**: Automated extraction of:
  - Statutes used by examiners
  - Claims rejected based on prior art
  - Prior art references cited (with passage locations)
  - Specific relevant sections in cited references

**Usage:**
- API syntax reference for enriched_client.py
- Field discovery and validation
- Lucene query construction and optimization
- Date coverage constraints for query building

**⚠️ Important Note:**
Unlike PFW, FPD, and PTAB the Citations API **does NOT have a Swagger/OpenAPI specification file**. This markdown document is the primary API reference available from USPTO. The API uses a generic DSAPI (Data Set API) framework rather than custom endpoints.

---

### `Document_Descriptions_List.csv`
**Source:** [USPTO EFS Document Description List](https://www.uspto.gov/patents/apply/filing-online/efs-info-document-description)
**Updated:** 04/27/2022
**Size:** ~189 KB (3,133 rows)

Comprehensive list of all USPTO document codes used in patent prosecution.

**Contents:**
- **3,100+ document codes** with official descriptions
- Categories: Amendments, Office Actions, Appeals, Citations, Filings, etc.
- Columns: Category, Document Description, USPTO Business Process, DOC CODE, FILING TYPE, NEW/FOLLOWON

**⚠️ Cross-MCP Integration Note:**
While the Citations MCP itself does **NOT download documents** (it returns citation metadata only), this reference file is critical for **Citations → PFW workflow integration**.

**Citation-Related Document Codes (Used with PFW MCP):**
- **CTFR** - Office Action (Non-Final Rejection) - *Where citations appear*
- **CTNF** - Office Action (Final Rejection) - *Where citations are cited*
- **NOA** - Notice of Allowance - *Citation context and examiner reasoning*
- **892** - Notice of References Cited - *Examiner's citation list*
- **IDS** - Information Disclosure Statement - *Applicant citations*
- **1449** - Information Disclosure Statement (PTO-1449) - *Applicant prior art*

**Usage in Citations → PFW Workflow:**
```python
# STEP 1: Citations - Get citation metadata
citations = search_citations_balanced(
    criteria='patentApplicationNumber:17896175',
    rows=20
)

# STEP 2: PFW - Get office action documents (where citations appear)
docs = pfw_get_application_documents(
    app_number='17896175',
    document_code='CTFR',  # From Document_Descriptions_List.csv
    limit=10
)

# STEP 3: PFW - Extract citation context
content = pfw_get_document_content(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
```

**Why This File is Included:**
1. Citations API returns **metadata only** (not documents)
2. PFW MCP provides the **actual office action documents** containing citation context
3. Document codes (especially 892, CTFR, NOA) are **referenced in citation workflows**
4. Essential for two-step **Citations → PFW integration** patterns

See `citations_get_guidance('workflows_pfw')` for complete integration workflows.

---

## Integration with MCP

### Citation Metadata vs Document Retrieval

**Citations MCP Provides:**
- Citation metadata (which patents/NPL were cited)
- Citation categories (X/Y/A/NPL)
- Examiner vs applicant citation indicators
- Related claims and passage locations (metadata)
- Office action dates and art unit context

**PFW MCP Provides (Required for Documents):**
- Actual office action PDFs (CTFR, NOA, 892)
- Document text extraction with OCR
- Complete prosecution history
- Examiner reasoning and citation context

### Two-Step Workflow Pattern

**Citations → PFW Integration** (Primary workflow):
1. **Citations**: Discover what was cited and when (metadata)
2. **PFW**: Retrieve office action documents for citation context (documents)

This two-step pattern is documented extensively in:
- `USAGE_EXAMPLES.md` - Example 3, Example 7
- `PROMPTS.md` - All prompt templates
- `citations_get_guidance('workflows_pfw')` - Workflow section

### Cross-MCP Integration Fields

**Citations → PFW:**
- `patentApplicationNumber` → `applicationNumberText` - Primary linking key
- `publicationNumber` → `patentNumber` - For granted patents
- `groupArtUnitNumber` - Art unit correlation
- Office action documents retrieved via PFW: CTFR, NOA, 892, IDS

**Citations → PTAB:**
- `publicationNumber` → `patentNumber` - Patent challenge correlation
- Prior art validation for IPR/PGR proceedings
- Vulnerability assessment based on citation patterns

**Citations → FPD:**
- `patentApplicationNumber` → `applicationNumber` - Petition correlation
- Prosecution quality assessment via citation density
- Petition red flags correlation with low citation counts

---

## API Architecture Notes

### No Swagger Specification Available

Unlike PFW, FPD and PTAB MCPs, the Citations API:
- **No OpenAPI/Swagger file** - Uses generic DSAPI framework
- **Field discovery via API** - `/v3/fields` endpoint returns available fields
- **Limited documentation** - Primary reference is the markdown file in this folder
- **22 total fields** (as of July 11, 2024) - Much smaller API surface than PFW/FPD/PTAB

### Field Discovery and Validation

The MCP includes runtime field discovery:
- `get_available_fields()` - Returns current API field list
- `validate_query()` - Validates Lucene syntax before execution
- `field_configs.yaml` - User-configurable field sets (minimal/balanced)

### AI/ML Data Extraction

The API uses sophisticated algorithms to extract:
- **Citation references** from office action documents (automated)
- **Claim mappings** for which claims were cited against
- **Passage locations** for specific prior art sections
- **Entity resolution** to consolidate applicant and examiner citations

This is **different from PFW/FPD** which provide structured data directly from USPTO databases. Citations API performs AI extraction from office action PDFs.

---

## Updating Reference Files

These files should be updated when:
1. **USPTO updates Citations API documentation** - Update `USPTO Enriched Citation API v3.md`
2. **New fields are added to Citations API** - Regenerate field_configs.yaml
3. **New document codes are added** - Update `Document_Descriptions_List.csv`

To update:
```bash
# Download latest Citations API documentation
# Visit: https://developer.uspto.gov/api-catalog/uspto-enriched-citation-api-v3
# Save as reference/USPTO Enriched Citation API v3.md

# Verify available fields via API
uv run python -c "from uspto_enriched_citation_mcp.main import get_available_fields; import asyncio; asyncio.run(get_available_fields())"

# Update document codes from USPTO EFS page (for PFW integration)
# Download from: https://www.uspto.gov/patents/apply/filing-online/efs-info-document-description
# Update reference/Document_Descriptions_List.csv

# Regenerate field configs if needed
# Edit field_configs.yaml manually (YAML-based, no code changes needed)
```

---

## Related Documentation

- **Tool Documentation:** See tool docstrings in `src/uspto_enriched_citation_mcp/main.py`
- **Field Configs:** See `field_configs.yaml` for progressive disclosure field sets
- **API Client:** See `src/uspto_enriched_citation_mcp/api/enriched_client.py` for implementation
- **Cross-MCP Workflows:** Use `citations_get_guidance('workflows_pfw')` for integration patterns
- **Usage Examples:** See `USAGE_EXAMPLES.md` for complete workflow examples
- **Prompt Templates:** See `PROMPTS.md` for guided workflow prompts

---

## Citation API Limitations & Constraints

### Date Coverage Constraint

**⚠️ CRITICAL**: Office actions from **October 1, 2017 to 30 days prior** to current date only.

**Implications:**
- Applications filed before ~2015 may have NO citation data (lag time to first OA)
- Always include date filter: `officeActionDate:[2017-10-01 TO *]`
- For application searches, use filing date `2015-01-01+` to account for lag

### Field Limitations

**Available Fields (22 total as of July 11, 2024):**
- Core: `citedDocumentIdentifier`, `patentApplicationNumber`, `publicationNumber`
- Citation: `citationCategoryCode`, `examinerCitedReferenceIndicator`
- Organizational: `groupArtUnitNumber`, `techCenter`, `workGroupNumber`
- Content: `passageLocationText`, `relatedClaimNumberText`, `officeActionCategory`

**Fields NOT Available (Must use PFW for these):**
- ❌ `examinerNameText` - **Must use PFW → Citations workflow**
- ❌ `firstApplicantName`
- ❌ `decisionTypeCode` / `decisionTypeCodeDescriptionText`
- ❌ Classification fields (USPC, CPC)

### Document Retrieval Constraint

**⚠️ CRITICAL**: Citations API provides **metadata only**, NOT documents.

**For actual documents, use PFW MCP:**
- Office action PDFs (CTFR, CTNF, NOA)
- Examiner citation lists (892)
- Applicant IDS documents (IDS, 1449)
- Text extraction with OCR (via `pfw_get_document_content`)

See `USAGE_EXAMPLES.md#example-7-cross-mcp-integration-with-pfw` for complete workflow.

---

## Notes

**Design Philosophy:**
- Citations MCP focuses on **citation metadata intelligence**
- PFW MCP provides **document retrieval and extraction**
- Together they enable **complete citation analysis with context**

**Workflow Efficiency:**
- Use Citations for **discovery and pattern analysis** (90-99% token reduction)
- Use PFW for **targeted document retrieval** (filtered by document codes)
- Progressive disclosure: Minimal → Balanced → Documents → Details

**Cross-MCP Synergy:**
- **Citations + PFW**: Complete prosecution citation context
- **Citations + PTAB**: Prior art validation for post-grant challenges
- **Citations + FPD**: Prosecution quality assessment via citation patterns
- **Citations + PFW + PTAB + FPD**: Complete lifecycle patent intelligence

This reference documentation supports the complete USPTO patent research ecosystem across all four specialized MCPs.
