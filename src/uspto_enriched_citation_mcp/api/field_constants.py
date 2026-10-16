"""
Field constants and definitions for USPTO Enriched Citation API.
"""

# Import field lists from configuration module (single source of truth)


# Field name constants
class CitationFields:
    """Field name constants for citation searches."""

    pass


# Query field name constants
class QueryFieldNames:
    """Query field name constants for building Lucene queries."""

    # Core identifier fields
    APPLICATION_NUMBER = "patentApplicationNumber"
    PUBLICATION_NUMBER = "publicationNumber"
    CITED_DOCUMENT_ID = "citedDocumentIdentifier"

    # Organizational fields
    TECH_CENTER = "techCenter"
    GROUP_ART_UNIT = "groupArtUnitNumber"
    WORK_GROUP = "workGroupNumber"

    # Citation metadata
    CITATION_CATEGORY = "citationCategoryCode"
    DECISION_TYPE_CODE = "decisionTypeCode"
    EXAMINER_CITED = "examinerCitedReferenceIndicator"
    APPLICANT_CITED = "applicantCitedExaminerReferenceIndicator"

    # Date fields
    OFFICE_ACTION_DATE = "officeActionDate"
    CREATE_DATE = "createDateTime"

    # Content fields
    PASSAGE_LOCATION = "passageLocationText"
    QUALITY_SUMMARY = "qualitySummaryText"
    RELATED_CLAIMS = "relatedClaimNumberText"
    OFFICE_ACTION_CATEGORY = "officeActionCategory"

    # Reference metadata
    INVENTOR_NAME = "inventorNameText"
    # FIRST_APPLICANT_NAME removed (MCP-2 / CQ-R-1, review 2026-09-28):
    # firstApplicantName is not a field on the enriched v3 API — field_configs.yaml
    # lists it under "Fields NOT Available in API v3" — so the applicant_name
    # convenience parameter that built a query against it could only ever
    # return zero results. Removed from tools/search.py and query_builder.py
    # rather than mapped, because no real field carries applicant/assignee
    # name on this API (verified against field_configs.yaml, reference/README.md
    # and reference/tool_guidance.md, none of which name a substitute); resolve
    # applicants through PFW instead.
    EXAMINER_NAME = "examinerNameText"  # May not be in API but used in code
    COUNTRY_CODE = "countryCode"
    KIND_CODE = "kindCode"
    NPL_INDICATOR = "nplIndicator"

    # System fields
    ID = "id"
    CREATE_USER = "createUserIdentifier"
    OBSOLETE_DOC = "obsoleteDocumentIdentifier"


# Field sets are imported from config.field_manager (single source of truth)
# MINIMAL_FIELDS and BALANCED_FIELDS defined at module level above
