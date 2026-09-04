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

Last validated: 2026-03-28 (STDIO + HTTP, Claude Desktop, 29/29 PASS)

Run in order. Tests marked ⭐ must complete before later tests that reference their output.

> **⚠ Identifier formats (crosswalk added 2026-09-02):** `application_number` is
> the application serial. `patent_number` now takes EITHER a granted patent number
> (7-8 digits; commas, spaces and a `US` prefix accepted) or an 11-digit pre-grant
> publication number, and **all four search tools resolve it themselves**: a granted
> number is crosswalked to its application serial with one USPTO ODP
> applications-search call and queried as `patentApplicationNumber`, while an
> 11-digit value queries `publicationNumber` (enriched lane only — the OA lane has
> no publication field and refuses it). Every response carries
> `patent_number_resolution` {input, interpreted_as, resolved_application_number when
> crosswalked, source}; assert on THAT first, since it is the part under test.
> Failures are 400s naming the accepted forms, not zero-results: an unresolvable
> number, a value that is neither 7-8 nor 11 digits, and a `patent_number` that
> disagrees with an `application_number` passed alongside it.
> **Fixture audit:** every 8-digit fixture in this suite is an APPLICATION serial
> passed as `application_number` or as a `patentApplicationNumber:` criteria clause
> (`11802002` Test 8, `12849948` Test 12, `13487597` OA Tests 5 and 10, `11588187`
> OA Test 6), so none depends on a lane interpretation. State the namespace when
> adding a fixture — an 8-digit value means a PATENT under `patent_number` and an
> APPLICATION under `application_number`.

---

> **Tool visibility caveat (2026-09-02):** `defer_loading: false` is advisory
> metadata that each client applies by its own policy, so an expected tool
> being invisible in a given client is not, by itself, a server defect. If a
> tool this suite calls does not appear in the client, record two facts
> separately: whether the server lists it (direct stdio or in-container probe
> of `tools/list`), and that this client did not. A tool the server does not
> list is a server defect and must be reported as one; a tool the server lists
> but the client hides is a client-visibility finding. Never fold one into the
> other. Load-bearing workflow content deliberately also rides in per-tool
> docstrings and return-path notes for exactly this reason.


## Enriched Citations (v3): 21 Tests

### Test 1: Tool Guidance

```
Citations_get_guidance
{
  "section": "tools"
}
```
**Expect:** Section listing all 10 tools with defer_loading status.

---

### Test 2: Get Available Fields

```
Citations_get_available_fields
{
}
```
**Expect:** 22 fields returned from Enriched Citations v3 API.

---

### Test 3: Minimal Search — Tech Center Discovery

```
Citations_search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5
}
```
**Expect:** ~4.2M numFound, 5 records with minimal fields. Tier = minimal.
Every record additionally carries `referenceKey` (added 2026-09-04), and the
envelope carries `rows_without_reference_identifier` whatever its value,
including 0.

---

### Test 4: Minimal Search — Date Range Discovery

```
Citations_search_citations_minimal
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
Citations_search_citations_minimal
{
  "criteria": "groupArtUnitNumber:2128",
  "rows": 5
}
```
**Expect:** ~47,000 numFound. All records show artUnit 2128.

---

### Test 5b: Minimal Search — examiner_cited + art_unit Convenience Parameters

```
Citations_search_citations_minimal
{
  "art_unit": "2128",
  "examiner_cited": true,
  "rows": 5
}
```
**Expect:** ~39,000 numFound (subset of ~47,000 total for AU:2128 — examiner filter excludes applicant-cited records). All results show groupArtUnitNumber=2128 and examinerCitedReferenceIndicator=true. Tier = minimal. Note: examiner_cited and art_unit are convenience params on both Citations_search_citations_minimal and Citations_search_citations_balanced (parity added 2026-03-28).

---

### Test 6: Minimal Search — Ultra-Minimal Custom Fields ⭐

```
Citations_search_citations_minimal
{
  "criteria": "techCenter:2100 AND examinerCitedReferenceIndicator:true",
  "fields": ["citedDocumentIdentifier", "patentApplicationNumber"],
  "rows": 5
}
```
**Expect:** Tier = ultra-minimal. Each doc has exactly 3-4 keys
(citedDocumentIdentifier, patentApplicationNumber, id, and `referenceKey`). No
other fields present. `referenceKey` is derived before the field filter runs,
so it is correct even when a custom list drops both source fields.

---

### Test 7: Balanced Search — X-Category Detailed Analysis ⭐

```
Citations_search_citations_balanced
{
  "criteria": "citationCategoryCode:X AND techCenter:2100",
  "rows": 2
}
```
**Expect:** passageLocationText and relatedClaimNumberText populated. Tier = balanced.

---

### Test 8: Balanced Search — Application Number Lookup

```
Citations_search_citations_balanced
{
  "application_number": "11802002",
  "rows": 5
}
```
**Expect:** patentApplicationNumber = 11802002 on all results. Passage data present.

---

### Test 9: Balanced Search — Publication Number Lookup (confirmed in dataset)

```
Citations_search_citations_balanced
{
  "patent_number": "20060075466",
  "rows": 3
}
```
**Expect:** ~5 numFound (live 2026-09-02), constructed_query `publicationNumber:20060075466`,
and `patent_number_resolution` = {input `20060075466`, interpreted_as `publication`,
queried_field `publicationNumber`} with NO `resolved_application_number` — an 11-digit
value is queried directly, not crosswalked. Previously used patent 11788453 which had 0
results — that was a coverage gap, not a bug.

---

### Test 9b: Balanced Search — Granted Patent Number Crosswalk ⭐

```
Citations_search_citations_balanced
{
  "patent_number": "7,971,071",
  "rows": 3
}
```
**Expect (primary assertion):** `patent_number_resolution` = {input `7,971,071`,
interpreted_as `granted_patent`, resolved_application_number **`11752072`**,
queried_field `patentApplicationNumber`, source `USPTO ODP applications search`}, and
constructed_query `patentApplicationNumber:11752072`. Commas are stripped, so
`7971071` and `US 7971071` must resolve identically.
**Secondary:** ~5 numFound (live 2026-09-02). Citation counts are the softer assertion —
the crosswalk is correct even if USPTO re-baselines the citation rows. Before the
crosswalk this same call went to `publicationNumber:7971071` and returned a clean 0.

Cross-check with an 8-digit granted number, where the shape collides with an
application serial: `patent_number: "10000000"` must resolve to application
**`14643719`** (~3 numFound enriched, ~2 OA, live 2026-09-02).

---

### Test 9c: Balanced Search — Unresolvable Patent Number Is an Error

```
Citations_search_citations_balanced
{
  "patent_number": "99999999"
}
```
**Expect:** `status: "error"`, `code: 400`, and an `error` naming all three accepted
forms (granted patent number, 11-digit publication number, application serial). No
search is issued. A 400 here is the point of the test: the old behavior was a
successful search with 0 rows, which reads as "this patent was never cited".
Same 400 class for `patent_number: "123456"` (wrong digit count) and for
`patent_number: "7971071"` passed together with `application_number: "16816197"`
(the two name different applications).

---

### Test 10: Balanced Search — Office Action Type Filter (CTNF)

```
Citations_search_citations_balanced
{
  "decision_type": "CTNF",
  "rows": 5
}
```
**Expect:** ~36M numFound. All results show officeActionCategory = CTNF (non-final rejection). Previously used "REJECTION" which returned 0 — fix maps decision_type to officeActionCategory field, values are CTNF/CTFR only.

---

### Test 11: Balanced Search — NPL via nplIndicator (corrected from citationCategoryCode:NPL)

```
Citations_search_citations_balanced
{
  "criteria": "nplIndicator:true AND techCenter:2100",
  "rows": 3
}
```
**Expect:** ~21,000 numFound. Previously used citationCategoryCode:NPL which returned 0 — NPL is identified by the nplIndicator boolean field, not as a category code value. Results will still have citationCategoryCode = X, Y, or A.

---

### Test 12: Get Citation Details — Full Record

```
Citations_get_citation_details
{
  "citation_id": "0de7ea10c59e03dab218a40dece9dffd",
  "include_context": true
}
```
**Expect:** Full record returned including passageLocationText, obsoleteDocumentIdentifier, and pfw_document_retrieval_guidance with CTNF as the suggested_document_code (app 12849948, officeActionCategory=CTNF — verified 2026-03-28).

---

### Test 13: Validate Query — Valid Lucene Syntax

```
Citations_validate_query
{
  "query": "citedDocumentIdentifier:US* AND officeActionDate:[2024-01-01 TO 2024-12-31]",
  "field_set": "citations_minimal"
}
```
**Expect:** valid = true, status = success.

---

### Test 14: Validate Query — Invalid Syntax Detection

```
Citations_validate_query
{
  "query": "techCenter 2100 AND missingField:value"
}
```
**Expect:** valid = false (missing colon in `techCenter 2100` detected).

---

### Test 15: Citation Statistics — Date-Scoped Aggregation

```
Citations_get_citation_statistics
{
  "criteria": "techCenter:2100 AND officeActionDate:[2024-01-01 TO 2024-12-31]"
}
```
**Expect:** total_citations ~265,000. breakdowns populated with Citation Category (X/Y/A counts) and Cited By (Examiner/Applicant counts). MCP App bar chart renders.

---

### Test 16: Citation Statistics — Multi-Art-Unit OR Query

```
Citations_get_citation_statistics
{
  "criteria": "groupArtUnitNumber:(2128 OR 2854) AND examinerCitedReferenceIndicator:true"
}
```
**Expect:** ~70,000 numFound. OR query across two art units working. breakdowns present.

---

### Test 16b: Citation Statistics is Enriched Lane Only (documented limit)

```
Citations_get_citation_statistics
{
  "criteria": "techCenter:2100 AND legalSectionCode:103"
}
```
**Expect:** `code: 400`, message `Invalid field name: legalSectionCode`
followed by the lane hint naming Citations_search_oa_citations_minimal/balanced
(added 2026-09-04). This tool aggregates the enriched lane only and has no
`lane` parameter; the OA index has no statistics path on this server. The
documented workaround is one OA search per bucket with `rows: 1`, reading
`response.numFound`.

---

### Test 17: Minimal Search — Complex Multi-Field Boolean

```
Citations_search_citations_minimal
{
  "criteria": "(techCenter:2100 OR techCenter:2800) AND citationCategoryCode:X AND examinerCitedReferenceIndicator:true AND officeActionDate:[2023-01-01 TO 2024-12-31]",
  "rows": 5
}
```
**Expect:** ~480,000 numFound. All 5 results have examinerCitedReferenceIndicator = true and citationCategoryCode = X.

---

### Test 18: Minimal Search — Pagination (Two Pages)

```
Citations_search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5,
  "start": 10
}
```
Then:
```
Citations_search_citations_minimal
{
  "criteria": "techCenter:2100",
  "rows": 5,
  "start": 13
}
```
**Expect:** First call returns records 11–15 (0-indexed: 10–14). Second call returns records 14–18. Records 14–15 overlap between the two pages (start=13 → records 13,14,15,16,17 share 13,14 with first call's 10,11,12,13,14).

---

## Office Action Citations (v2): 11 Tests

### OA Test 1: Field Discovery

```
Citations_get_oa_citation_fields
{
}
```
**Expect:** 16 fields returned. API identified as oa_citations_v2. Coverage note about Form 892 (examiner) and Form 1449 (applicant).

---

### OA Test 2: Minimal Search — Tech Center Discovery

```
Citations_search_oa_citations_minimal
{
  "criteria": "techCenter:2600",
  "rows": 5
}
```
**Expect:** ~6.2M numFound (was ~14M before the ~2025-07 USPTO OA v2 dataset re-baseline; verified against the raw API 2026-07-09 — still larger than the enriched dataset). Records have referenceIdentifier and actionTypeCategory present where populated, plus `parsedReferenceIdentifier` (added to the minimal tier 2026-09-04) and the derived `referenceKey`. `legalSectionCode` is balanced-only and must NOT appear on this tier.

---

### OA Test 3: Minimal Search — Art Unit + Examiner-Cited Convenience Params

```
Citations_search_oa_citations_minimal
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
Citations_search_oa_citations_minimal
{
  "criteria": "legalSectionCode:103 AND techCenter:2600",
  "rows": 5
}
```
**Expect:** numFound confirms §103 is the most common rejection type. The clause filters server-side, but `legalSectionCode` is a balanced-tier field and is NOT returned on the minimal rows; to see the value, use `Citations_search_oa_citations_balanced` or pass an explicit `fields` list.

---

### OA Test 5: Minimal Search — Application Number Lookup ⭐

```
Citations_search_oa_citations_minimal
{
  "criteria": "patentApplicationNumber:13487597",
  "rows": 10
}
```
**Expect:** All results for app 13487597. Mix of examiner-cited and applicant-cited indicators. Note total OA citation count for this application. `legalSectionCode` is NOT on this tier (balanced only), but `parsedReferenceIdentifier` and `referenceKey` are.

---

### OA Test 6: Balanced Search — Full Record Analysis

```
Citations_search_oa_citations_balanced
{
  "criteria": "patentApplicationNumber:11588187 AND legalSectionCode:112",
  "rows": 5
}
```
**Expect:** `numFound = 6`, all records legalSectionCode = 112 (art unit 2646, TC2600). Unfiltered `patentApplicationNumber:11588187` returns 18 rows, so the section filter demonstrably narrows. Full 16-field records with legalSectionCode, parsedReferenceIdentifier, workGroup populated where available; `paragraphNumber` is sparsely populated across the whole OA dataset and may be absent on every row (normal, not a defect).

> Re-anchored 2026-09-02: the previous fixture (app 14633232, "has §112
> rejections confirmed in test data") no longer holds after the upstream OA
> re-baseline; that app now carries 10 rows, all §103, and
> `legalSectionCode:112` on it returns numFound = 0 (verified live).

---

### OA Test 7: Balanced Search — Rejected §103 Filter

```
Citations_search_oa_citations_balanced
{
  "criteria": "actionTypeCategory:rejected AND legalSectionCode:103 AND techCenter:2600",
  "rows": 3
}
```
**Expect:** All results show actionTypeCategory = rejected and legalSectionCode = 103. passageLocationText NOT present (this is OA v2 raw data, not AI-enriched). Cross-reference point: same references may appear in enriched citations with passage text.

---

### OA Test 8: Minimal Search — Custom Fields (Ultra-Minimal, confirms OA-5 fix)

```
Citations_search_oa_citations_minimal
{
  "criteria": "legalSectionCode:102 AND techCenter:2600",
  "fields": ["patentApplicationNumber", "referenceIdentifier", "legalSectionCode"],
  "rows": 5
}
```
**Expect:** Each doc contains patentApplicationNumber, referenceIdentifier, legalSectionCode (plus possibly id), the derived `referenceKey`, AND a per-row `_pfw_link`. The `_pfw_link` on a CUSTOM `fields` list is DELIBERATE, not leakage: the 2026-08-30 dedupe moved the PFW hand-off to a single envelope `pfw_link` for default-shape responses, but a caller who chose the doc shape keeps the established inline per-row annotation (pinned by eval `tr-hp-07`). Previously bug: API ignored fl parameter; fix does client-side field filtering in oa_citation_service.py. Tier = custom in query_info.

---

### OA Test 9: Minimal Search — Date Range

```
Citations_search_oa_citations_minimal
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
Citations_search_citations_minimal
{
  "application_number": "13487597",
  "rows": 10
}
```

Step 2 — get OA citations for same application:
```
Citations_search_oa_citations_minimal
{
  "criteria": "patentApplicationNumber:13487597",
  "rows": 10
}
```
**Expect:** OA v2 should return more raw citations than enriched v3 (broader coverage, includes citations not yet AI-processed). **Union the two lanes on `referenceKey`, never on the raw identifier fields.** Comparing OA `parsedReferenceIdentifier` against enriched `citedDocumentIdentifier` finds zero overlap on every application, because the lanes write the same reference differently (measured on app 12849948, 2026-09-04: `20060075466` against `US 2006/0075466 A1`, when four references are in fact in both lanes). Enriched rows whose `referenceKey` is null are counted on the envelope as `rows_without_reference_identifier`; report them as unresolved rather than dropping them. This validates the cross-check workflow documented in the guidance.

---

### OA Test 11: Minimal Search — Granted Patent Number Crosswalk

```
Citations_search_oa_citations_minimal
{
  "patent_number": "7971071",
  "rows": 10
}
```
**Expect (primary assertion):** `patent_number_resolution` = {input `7971071`,
interpreted_as `granted_patent`, resolved_application_number **`11752072`**,
queried_field `patentApplicationNumber`, source `USPTO ODP applications search`}, and
constructed_query `patentApplicationNumber:11752072`. This lane had no patent-number
path at all before the crosswalk (`publicationNumber` returns 400 as a field, and still
does — the parameter is the only way in).
**Secondary:** ~5 numFound (live 2026-09-02), all rows on application 11752072.

Two refusals to spot-check, both `code: 400` with no search issued:
`patent_number: "20060075466"` (an 11-digit publication number, which this index cannot
search — the message points at Citations_search_citations_minimal) and
`patent_number: "7971071"` together with `application_number: "16816197"` (conflicting
identifiers).

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
| 1449/IDS undercount | Neither lane holds the applicant's full IDS, in any era. Union of BOTH lanes against the patents' own References Cited pages: US 7,971,071 5 of 91; US 9,496,922 1 of 251; US 9,135,462 0 of ~620; US 11,656,067 (2021-2023, inside the documented window) 3 of 15. Disclosed in both OA search tool descriptions since 2026-09-04. A reference's absence is not evidence it was not disclosed |
| Cross-lane union key | `referenceKey` on every row of every tier on both lanes (2026-09-04). Digits only: a leading US, spaces, slashes, hyphens and the kind code stripped, series markers such as RE kept. Null when the identifier does not reduce to a document number |
| Blank enriched references | Absent, null and empty `citedDocumentIdentifier` are ONE state, and can pair with an empty `publicationNumber`. Counted on the enriched envelope as `rows_without_reference_identifier` (2 of 5 on 11752072, 4 of 8 on 12849948, 4 of 26 on 18407147) |
| OA `publicationNumber` 400 | Deliberate. The raw upstream API answers that field with HTTP 200 and numFound 0, which reads as "never cited". A visible refusal beats a silent zero |
| Date coverage | officeActionDate from 2017-10-01 forward; pre-2017 dates in dataset may reflect filing/creation dates |
| Patent lookup | Not all US patents appear — only those cited in an OA covered by the API |
| OA legalSectionCode values | 102, 103, 112, **and "Other"** — filter pills should handle "Other" gracefully |
| OA actionTypeCategory values | rejected, withdrawn, interpreted, **and "objected"** — more values than initially assumed |
| OA cross-check gap | App 13487597: 0 enriched citations vs 8 OA citations (19 pre-re-baseline) — OA v2 has broader raw coverage of records not yet AI-processed into enriched set |
| NPL in enriched balanced results | qualitySummaryText may contain "#6: NPL was used in the rejection" — useful signal even without a dedicated NPL category code |
