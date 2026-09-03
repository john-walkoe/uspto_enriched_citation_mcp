"""Tool registration package (SD-1/SOLID-1 god-module split).

Each module defines its tools as plain (envelope-wrapped) async functions and
exposes register(mcp); register_all preserves the historical registration
order from the pre-split main.py: Citations_get_available_fields ->
Citations_search_citations_* -> Citations_get_citation_details ->
Citations_validate_query -> Citations_get_citation_statistics ->
Citations_get_guidance -> Citations_search_oa_citations_* ->
Citations_get_oa_citation_fields -> citations_manage_users (conditional). Because utility.py's three tools were
interleaved with the other categories in that original order, register_all
calls its granular register_fields/register_validate/register_guidance
functions individually rather than utility.register() (which groups all
three together for standalone use).
"""

from . import admin, details, oa, search, statistics, utility


def register_all(mcp, auth_provider=None) -> None:
    utility.register_fields(mcp)      # Citations_get_available_fields
    search.register(mcp)              # Citations_search_citations_minimal, _balanced
    details.register(mcp)             # Citations_get_citation_details
    utility.register_validate(mcp)    # Citations_validate_query
    statistics.register(mcp)          # Citations_get_citation_statistics
    utility.register_guidance(mcp)    # Citations_get_guidance
    oa.register(mcp)                  # Citations_search_oa_citations_*, Citations_get_oa_citation_fields
    admin.register(mcp, auth_provider)  # citations_manage_users (conditional)
