"""
Field constants and definitions for USPTO Enriched Citation API.
"""

# Import field lists from configuration module (single source of truth)
from ..config.field_manager import (
    DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS,
    DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS,
)


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
    FIRST_APPLICANT_NAME = "firstApplicantName"  # May not be in API but used in code
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
