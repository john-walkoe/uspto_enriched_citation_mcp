"""
USPTO Office Action Citations API v2 client.

Concrete client for the /api/v1/patent/oa/oa_citations/v2 endpoint.
Shares transport, caching, and resilience logic with EnrichedCitationClient via
BaseCitationClient.
"""

from typing import Dict, List, Optional

from .base_citation_client import BaseCitationClient
from ..config.constants import (
    OA_CITATIONS_FIELDS_PATH,
    OA_CITATIONS_RECORDS_PATH,
)
from ..shared.circuit_breaker import uspto_api_breaker  # re-exported for backward compat


# OA Citations v2 field sets (kept here so callers can import them directly)
OA_CITATIONS_MINIMAL_FIELDS = [
    "patentApplicationNumber",
    "groupArtUnitNumber",
    "techCenter",
    "referenceIdentifier",
    "actionTypeCategory",
    "examinerCitedReferenceIndicator",
    "createDateTime",
]

OA_CITATIONS_ALL_FIELDS = [
    "patentApplicationNumber",
    "groupArtUnitNumber",
    "techCenter",
    "referenceIdentifier",
    "parsedReferenceIdentifier",
    "actionTypeCategory",
    "legalSectionCode",
    "examinerCitedReferenceIndicator",
    "applicantCitedExaminerReferenceIndicator",
    "officeActionCitationReferenceIndicator",
    "workGroup",
    "paragraphNumber",
    "createDateTime",
    "createUserIdentifier",
    "obsoleteDocumentIdentifier",
    "id",
]


class OACitationsClient(BaseCitationClient):
    """
    Async HTTP client for USPTO Office Action Citations API v2.

    Shares the same ODP base URL and X-API-KEY auth as PFW/PTAB/FPD/Enriched
    Citations.  Uses form-encoded POST body (same as enriched citations API).

    Inherits shared transport, caching, rate-limiting, and resilience logic
    from BaseCitationClient.
    """

    _FIELDS_PATH = OA_CITATIONS_FIELDS_PATH
    _RECORDS_PATH = OA_CITATIONS_RECORDS_PATH
    _CACHE_KEY_PREFIX = "oa"

    # Override get_fields / search_records to inherit base-class behaviour.
    # The base class uses self._FIELDS_PATH, self._RECORDS_PATH, and
    # self._CACHE_KEY_PREFIX automatically.
    #
    # Only the public method signatures (which match the original API) are
    # exposed here; _get_fields_impl / _search_records_impl come from the base.
