# USPTO Enriched Citation API v3

**Source:** [USPTO Open Data Portal — Enriched Citations](https://data.uspto.gov/apis/enriched-citations/search)
**Updated:** March 2026

---

## API Overview

The Enriched Citation API provides the IP5 and the public with greater insight into the patent evaluation process, and marks one of the first production implementations of the usage of artificial intelligence (AI) for data extraction at the USPTO. It allows users to quickly view information about which references, or prior art, were cited in specific patent application office actions, including:

- Bibliographic information of the reference
- The claims that the prior art was cited against
- The relevant sections that the examiner relied upon

The API allows for daily refresh and retrieval of enriched citation data from Office Actions mailed from **October 1, 2017, to 30 days prior to the current date**.

Empowered by state-of-the-art machine learning, AI, and natural language processing algorithms, the enriched citation API analyzes the structure and content of office actions. The API then uses sophisticated information extraction and entity extraction algorithms to accurately locate:

- The statutes used by examiners
- The claims rejected based on prior art
- The specific prior art references cited
- Specific relevant sections in the cited prior art references used

An entity resolution algorithm is then used to consolidate the extraction results with the reference lists in the application, including references cited by applicants and by examiners. The process is fully automated and highly tunable, and able to incorporate feedback from manual reviewers to improve efficiency and accuracy.

---

## API Endpoint

**POST** `https://api.uspto.gov/api/v1/patent/oa/enriched_cited_reference_metadata/v3/records`

Returns a list of all Enriched Citations that match your search term.

**Note:** API Key required (`X-API-KEY` header).

See the Swagger documentation link on the [API page](https://data.uspto.gov/apis/enriched-citations/search) for the full OpenAPI spec.

### Request Parameters

| Parameter | Description | Type |
|-----------|-------------|------|
| `criteria` | Lucene query string (e.g. `patentApplicationNumber:17896175`) | String |
| `start` | Starting record number (default: 0) | Integer |
| `rows` | Number of rows to return | Integer |
| `fl` | Comma-separated field list to return (field filtering) | String |

---

## Response Fields

| Field | Description | Type |
|-------|-------------|------|
| `officeActionDate` | The date the office action was recorded | Date |
| `relatedClaimNumberText` | Claims related to current citation | String |
| `applicantCitedExaminerReferenceIndicator` | Whether citation was from Form PTO-1449 (applicant-submitted) | Boolean |
| `createUserIdentifier` | Job identifier that initiated the database insert | String |
| `officeActionCategory` | CTNF (non-final rejection) or CTFR (final rejection) | String |
| `patentApplicationNumber` | Two-digit series code + six-digit serial number | String |
| `inventorNameText` | Citation document title, company name, inventor, or owner | String |
| `groupArtUnitNumber` | Four-digit examiner team code (first two digits = tech center) | String |
| `qualitySummaryText` | Quality summary of the review (AOK, or issue codes 1–6) | String |
| `createDateTime` | Date/time entity was inserted in database | Date |
| `techCenter` | Four-digit technology center code | String |
| `citedDocumentIdentifier` | Patent number or publication number of cited document | String |
| `passageLocationText` | Passage locations related to current citation | String |
| `obsoleteDocumentIdentifier` | Unique IFW repository document identifier | String |
| `citationCategoryCode` | Relevance category: X, Y, A, E, L, O, T, P, &, D | String |
| `id` | Unique record identifier | String |
| `examinerCitedReferenceIndicator` | Whether citation was from Form PTO-892 (examiner-submitted) | Boolean |
| `nplIndicator` | Whether citation is non-patent literature | Boolean |
| `publicationNumber` | Publication number of cited patent | String |
| `kindCode` | Kind code of cited document | String |
| `workGroupNumber` | Work group subdivision within art unit | String |
| `countryCode` | Country code of cited document | String |

**Important field notes:**
- `officeActionCategory` values: `CTNF` = Non-Final Rejection, `CTFR` = Final Rejection
- For NPL (non-patent literature) queries use `nplIndicator:true` — `citationCategoryCode:NPL` returns zero results
- `examinerCitedReferenceIndicator:true` = Form 892 (examiner); `applicantCitedExaminerReferenceIndicator:true` = Form 1449 (applicant)

---

## Sample JSON Response

```json
{
  "response": {
    "start": 0,
    "numFound": 3,
    "docs": [
      {
        "relatedClaimNumberText": "1,7",
        "officeActionDate": "2019-10-21T00:00:00",
        "createUserIdentifier": "ETL_SYS",
        "applicantCitedExaminerReferenceIndicator": false,
        "kindCode": "A1",
        "nplIndicator": false,
        "workGroupNumber": "2830",
        "patentApplicationNumber": "15739603",
        "officeActionCategory": "CTNF",
        "inventorNameText": "Supriya; Amrit",
        "groupArtUnitNumber": "2837",
        "qualitySummaryText": "AOK",
        "createDateTime": "2026-03-02T21:36:52",
        "techCenter": "2800",
        "citedDocumentIdentifier": "US 20190165601 A1",
        "countryCode": "US",
        "passageLocationText": [
          "c. 103|claim 1|claims 1 and 7|claim 2|claims 16-22"
        ],
        "obsoleteDocumentIdentifier": "K1V5RMZ8RXEAPX0",
        "id": "d7e95803517f677b3875dc476a61a817",
        "citationCategoryCode": "Y",
        "examinerCitedReferenceIndicator": true,
        "publicationNumber": "20190165601"
      }
    ]
  }
}
```

---

## Lucene Query Parser Syntax

This API uses Solr/Lucene search. Query the `criteria` parameter using the following syntax.

### Overview

The Query Parser interprets a string into a Lucene Query. Each field or combination of fields can be searched using the syntax options shown below.

### Terms

A query is broken up into terms and operators. There are two types of terms:
- **Single Term**: a single word such as `test` or `hello`
- **Phrase**: a group of words in double quotes such as `"hello dolly"`

### Fields

Search any field by typing `fieldname:value`:

```
patentApplicationNumber:17896175
officeActionCategory:CTNF
groupArtUnitNumber:2837
```

### Wildcard Searches

- Single character wildcard: `?` (e.g. `te?t` matches `text` or `test`)
- Multiple character wildcard: `*` (e.g. `test*` matches `test`, `tests`, `tester`)
- Note: `*` or `?` cannot be the first character of a search

### Fuzzy Searches

Use `~` at the end of a single word term: `roam~`

Optional similarity parameter (0–1): `roam~0.8`

### Proximity Searches

Use `~` at the end of a phrase with a word distance: `"office action"~10`

### Range Searches

Inclusive (square brackets): `officeActionDate:[2020-01-01 TO 2021-01-01]`

Exclusive (curly brackets): `officeActionDate:{2020-01-01 TO 2021-01-01}`

Open-ended: `officeActionDate:[2017-10-01 TO *]`

### Boosting a Term

Use `^` with a boost factor: `patentApplicationNumber:17896175^4 groupArtUnitNumber:2837`

### Boolean Operators

Boolean operators must be ALL CAPS.

| Operator | Meaning | Example |
|----------|---------|---------|
| `OR` | Either term (default) | `CTNF OR CTFR` |
| `AND` | Both terms required | `patentApplicationNumber:17896175 AND examinerCitedReferenceIndicator:true` |
| `NOT` | Exclude term | `officeActionCategory:CTNF NOT nplIndicator:true` |
| `+` | Required term | `+patentApplicationNumber:17896175 groupArtUnitNumber:2837` |
| `-` | Prohibited term | `officeActionCategory:CTNF -nplIndicator:true` |
| `&&` | AND shorthand | `criteria1 && criteria2` |
| `\|\|` | OR shorthand | `criteria1 \|\| criteria2` |

### Grouping

Use parentheses to group clauses:

```
(CTNF OR CTFR) AND patentApplicationNumber:17896175
```

### Field Grouping

Group multiple clauses for a single field:

```
officeActionCategory:(+CTNF +"CTFR")
```

### Escaping Special Characters

Escape these special characters with `\`:

```
+ - && || ! ( ) { } [ ] ^ " ~ * ? : \
```

Example: `\(1\+1\)\:2` searches for `(1+1):2`
