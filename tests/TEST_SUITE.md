# USPTO Enriched Citation MCP — Test Suite

## What this is

A manual test suite for verifying MCP tool behavior using **Claude Desktop** (or any MCP client).
These are not unit tests — they are end-to-end confirmations that each tool works correctly against
the live USPTO API with known inputs and expected outputs.

**Who it's for:** Developers building on or extending this MCP who want confidence that the tools
behave as documented before making changes. Run it after setup, after upgrades, or after modifying
tool logic.

## How to run

1. Open Claude Desktop (or your MCP client) with this server connected
2. Paste the following prompt to kick off the whole suite in one go:

> **"Please perform these MCP tests in order. For each test, call the tool with the parameters shown
> and tell me whether the result matches the expected output. Report PASS, PARTIAL, or FAIL for each."**
> *(then paste the test cases you want to run below that prompt)*

3. Or run tests individually — copy a tool name + JSON block and prompt Claude with:
   *"Call `[tool_name]` with these parameters: `[paste JSON]`"*
4. Compare each response against the **Expect** line
5. Tests marked ⭐ produce output needed by a later test — note the value before continuing

Both STDIO and HTTP transport modes should pass all tests. Last validated: 2026-07-09 (STDIO via
Claude Code, all tool-invocable tests PASS after the audit-remediation refactor; MCP App iframe
rendering requires Claude Desktop). Two live regressions in the newly-activated OA query validation
(OA-only field names, ISO-8601 timestamps in ranges) were found by this suite and fixed same-day.
Note: USPTO re-baselined the OA v2 dataset (~2025-07 ETL reload) — several OA numFound anchors
dropped; updated below. Prior full validation: 2026-03-28 (29/29 PASS, both modes).

---

Feature branch: `feature/api-update-and-fastmcp-3`
Last validated: 2026-03-28 (STDIO + HTTP, Claude Desktop, 29/29 PASS)

Run in order. Tests marked ⭐ must complete before later tests that reference their output.

---

## Enriched Citations (v3) — 18 Tests

### Test 1: Tool Guidance

```
citations_get_guidance
{
  "section": "tools"
}
```
**Expect:** Section listing all 10 tools with defer_loading status.

---

### Test 2: Get Available Fields

```
get_available_fields
{
}
```
**Expect:** 22 fields returned from Enriched Citations v3 API.

---

### Test 3: Minimal Search — Tech Center Discovery

```
search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5
}
```
**Expect:** ~4.2M numFound, 5 records with minimal fields. Tier = minimal.

---

### Test 4: Minimal Search — Date Range Discovery

```
search_citations_minimal
{
  "date_start": "2024-01-01",
  "date_end": "2024-12-31",
  "rows": 5
}
```
**Expect:** ~2.84M numFound, all officeActionDate values within 2024.

---

### Test 5: Minimal Search — Art Unit Discovery

```
search_citations_minimal
{
  "criteria": "groupArtUnitNumber:2128",
  "rows": 5
}
```
**Expect:** ~47,000 numFound. All records show artUnit 2128.

---

### Test 5b: Minimal Search — examiner_cited + art_unit Convenience Parameters

```
search_citations_minimal
{
  "art_unit": "2128",
  "examiner_cited": true,
  "rows": 5
}
```
**Expect:** ~39,000 numFound (subset of ~47,000 total for AU:2128 — examiner filter excludes applicant-cited records). All results show groupArtUnitNumber=2128 and examinerCitedReferenceIndicator=true. Tier = minimal. Note: examiner_cited and art_unit are convenience params on both search_citations_minimal and search_citations_balanced (parity added 2026-03-28).

---

### Test 6: Minimal Search — Ultra-Minimal Custom Fields ⭐

```
search_citations_minimal
{
  "criteria": "techCenter:2100 AND examinerCitedReferenceIndicator:true",
  "fields": ["citedDocumentIdentifier", "patentApplicationNumber"],
  "rows": 5
}
```
**Expect:** Tier = ultra-minimal. Each doc has exactly 2-3 keys (citedDocumentIdentifier, patentApplicationNumber, id). No other fields present.

---

### Test 7: Balanced Search — X-Category Detailed Analysis ⭐

```
search_citations_balanced
{
  "criteria": "citationCategoryCode:X AND techCenter:2100",
  "rows": 2
}
```
**Expect:** passageLocationText and relatedClaimNumberText populated. Tier = balanced.

---

### Test 8: Balanced Search — Application Number Lookup

```
search_citations_balanced
{
  "application_number": "11802002",
  "rows": 5
}
```
**Expect:** patentApplicationNumber = 11802002 on all results. Passage data present.

---

### Test 9: Balanced Search — Patent Number Lookup (confirmed in dataset)

```
search_citations_balanced
{
  "patent_number": "20060075466",
  "rows": 3
}
```
**Expect:** Results returned (this publicationNumber is confirmed present in dataset). Previously used patent 11788453 which had 0 results — that was a coverage gap, not a bug.

---

### Test 10: Balanced Search — Office Action Type Filter (CTNF)

```
search_citations_balanced
{
  "decision_type": "CTNF",
  "rows": 5
}
```
**Expect:** ~36M numFound. All results show officeActionCategory = CTNF (non-final rejection). Previously used "REJECTION" which returned 0 — fix maps decision_type to officeActionCategory field, values are CTNF/CTFR only.

---

### Test 11: Balanced Search — NPL via nplIndicator (corrected from citationCategoryCode:NPL)

```
search_citations_balanced
{
  "criteria": "nplIndicator:true AND techCenter:2100",
  "rows": 3
}
```
**Expect:** ~21,000 numFound. Previously used citationCategoryCode:NPL which returned 0 — NPL is identified by the nplIndicator boolean field, not as a category code value. Results will still have citationCategoryCode = X, Y, or A.

---

### Test 12: Get Citation Details — Full Record

```
get_citation_details
{
  "citation_id": "0de7ea10c59e03dab218a40dece9dffd",
  "include_context": true
}
```
**Expect:** Full record returned including passageLocationText, obsoleteDocumentIdentifier, and pfw_document_retrieval_guidance with CTNF as the suggested_document_code (app 12849948, officeActionCategory=CTNF — verified 2026-03-28).

---

### Test 13: Validate Query — Valid Lucene Syntax

```
validate_query
{
  "query": "citedDocumentIdentifier:US* AND officeActionDate:[2024-01-01 TO 2024-12-31]",
  "field_set": "citations_minimal"
}
```
**Expect:** valid = true, status = success.

---

### Test 14: Validate Query — Invalid Syntax Detection

```
validate_query
{
  "query": "techCenter 2100 AND missingField:value"
}
```
**Expect:** valid = false (missing colon in `techCenter 2100` detected).

---

### Test 15: Citation Statistics — Date-Scoped Aggregation

```
get_citation_statistics
{
  "criteria": "techCenter:2100 AND officeActionDate:[2024-01-01 TO 2024-12-31]"
}
```
**Expect:** total_citations ~265,000. breakdowns populated with Citation Category (X/Y/A counts) and Cited By (Examiner/Applicant counts). MCP App bar chart renders.

---

### Test 16: Citation Statistics — Multi-Art-Unit OR Query

```
get_citation_statistics
{
  "criteria": "groupArtUnitNumber:(2128 OR 2854) AND examinerCitedReferenceIndicator:true"
}
```
**Expect:** ~70,000 numFound. OR query across two art units working. breakdowns present.

---

### Test 17: Minimal Search — Complex Multi-Field Boolean

```
search_citations_minimal
{
  "criteria": "(techCenter:2100 OR techCenter:2800) AND citationCategoryCode:X AND examinerCitedReferenceIndicator:true AND officeActionDate:[2023-01-01 TO 2024-12-31]",
  "rows": 5
}
```
**Expect:** ~480,000 numFound. All 5 results have examinerCitedReferenceIndicator = true and citationCategoryCode = X.

---

### Test 18: Minimal Search — Pagination (Two Pages)

```
search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5,
  "start": 10
}
```
Then:
```
search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5,
  "start": 13
}
```
**Expect:** First call returns records 11–15 (0-indexed: 10–14). Second call returns records 14–18. Records 14–15 overlap between the two pages (start=13 → records 13,14,15,16,17 share 13,14 with first call's 10,11,12,13,14).

---

## Office Action Citations (v2) — 10 Tests

### OA Test 1: Field Discovery

```
get_oa_citation_fields
{
}
```
**Expect:** 16 fields returned. API identified as oa_citations_v2. Coverage note about Form 892 (examiner) and Form 1449 (applicant).

---

### OA Test 2: Minimal Search — Tech Center Discovery

```
search_oa_citations_minimal
{
  "criteria": "techCenter:2600",
  "rows": 5
}
```
**Expect:** ~6.2M numFound (was ~14M before the ~2025-07 USPTO OA v2 dataset re-baseline; verified against the raw API 2026-07-09 — still larger than the enriched dataset). Records have referenceIdentifier, actionTypeCategory, legalSectionCode present where populated.

---

### OA Test 3: Minimal Search — Art Unit + Examiner-Cited Convenience Params

```
search_oa_citations_minimal
{
  "art_unit": "2626",
  "examiner_cited": true,
  "rows": 5
}
```
**Expect:** All results have examinerCitedReferenceIndicator = true and groupArtUnitNumber = 2626.

---

### OA Test 4: Minimal Search — Legal Section Code Filter (§103)

```
search_oa_citations_minimal
{
  "criteria": "legalSectionCode:103 AND techCenter:2600",
  "rows": 5
}
```
**Expect:** All returned records show legalSectionCode = 103. numFound confirms §103 is most common rejection type.

---

### OA Test 5: Minimal Search — Application Number Lookup ⭐

```
search_oa_citations_minimal
{
  "criteria": "patentApplicationNumber:13487597",
  "rows": 10
}
```
**Expect:** All results for app 13487597. Mix of examiner-cited and applicant-cited indicators. Multiple legalSectionCode values possible (102, 103, 112). Note total OA citation count for this application.

---

### OA Test 6: Balanced Search — Full Record Analysis

```
search_oa_citations_balanced
{
  "criteria": "patentApplicationNumber:14633232",
  "rows": 5
}
```
**Expect:** Full 16-field records. legalSectionCode, paragraphNumber, parsedReferenceIdentifier, workGroup all populated where available. App 14633232 has §112 rejections confirmed in test data.

---

### OA Test 7: Balanced Search — Rejected §103 Filter

```
search_oa_citations_balanced
{
  "criteria": "actionTypeCategory:rejected AND legalSectionCode:103 AND techCenter:2600",
  "rows": 3
}
```
**Expect:** All results show actionTypeCategory = rejected and legalSectionCode = 103. passageLocationText NOT present (this is OA v2 raw data, not AI-enriched). Cross-reference point: same references may appear in enriched citations with passage text.

---

### OA Test 8: Minimal Search — Custom Fields (Ultra-Minimal, confirms OA-5 fix)

```
search_oa_citations_minimal
{
  "criteria": "legalSectionCode:102 AND techCenter:2600",
  "fields": ["patentApplicationNumber", "referenceIdentifier", "legalSectionCode"],
  "rows": 5
}
```
**Expect:** Each doc contains ONLY patentApplicationNumber, referenceIdentifier, legalSectionCode (plus possibly id). Previously bug: API ignored fl parameter; fix does client-side field filtering in oa_citation_service.py. Tier = custom in query_info.

---

### OA Test 9: Minimal Search — Date Range

```
search_oa_citations_minimal
{
  "criteria": "techCenter:2600 AND createDateTime:[2025-01-01T00:00:00Z TO 2025-12-31T23:59:59Z]",
  "rows": 5
}
```
**Expect:** Records with createDateTime within 2025. Confirms date field syntax for OA v2 (createDateTime vs officeActionDate used in enriched citations).

---

### OA Test 10: Cross-Check — Enrich ↔ OA Comparison for Same Application

Step 1 — get enriched citations for an application:
```
search_citations_minimal
{
  "application_number": "13487597",
  "rows": 10
}
```

Step 2 — get OA citations for same application:
```
search_oa_citations_minimal
{
  "criteria": "patentApplicationNumber:13487597",
  "rows": 10
}
```
**Expect:** OA v2 should return more raw citations than enriched v3 (broader coverage, includes citations not yet AI-processed). Compare referenceIdentifier / citedDocumentIdentifier values between the two datasets. This validates the cross-check workflow documented in the guidance.

---

## Quick Reference: Known Dataset Characteristics

| Observation | Notes |
|-------------|-------|
| Valid category codes | X, Y, A only — `citationCategoryCode:NPL` returns 0 |
| NPL identification | Use `nplIndicator:true` (boolean), not a category code |
| Office action type field | `officeActionCategory` — values: `CTNF` (non-final), `CTFR` (final) |
| `decisionTypeCode` | Present in schema but unpopulated — don't use |
| PFW document retrieval | Use `document_code='CTNF'` to get non-final OA (most citations) |
| OA v2 `fl` parameter | API ignores it — client-side filtering applied in oa_citation_service.py |
| OA dataset size | re-baselined ~2025-07: TC:2600 now ~6.2M (was ~14M); still broader raw coverage than enriched |
| Applicant cited count | Often 0 in statistics — most IDS submissions are not coded in this dataset |
| Date coverage | officeActionDate from 2017-10-01 forward; pre-2017 dates in dataset may reflect filing/creation dates |
| Patent lookup | Not all US patents appear — only those cited in an OA covered by the API |
| OA legalSectionCode values | 102, 103, 112, **and "Other"** — filter pills should handle "Other" gracefully |
| OA actionTypeCategory values | rejected, withdrawn, interpreted, **and "objected"** — more values than initially assumed |
| OA cross-check gap | App 13487597: 0 enriched citations vs 8 OA citations (19 pre-re-baseline) — OA v2 has broader raw coverage of records not yet AI-processed into enriched set |
| NPL in enriched balanced results | qualitySummaryText may contain "#6: NPL was used in the rejection" — useful signal even without a dedicated NPL category code |
