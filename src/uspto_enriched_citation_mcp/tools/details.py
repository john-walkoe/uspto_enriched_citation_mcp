"""Enriched Citations (v3) single-citation detail tool."""

import re
from typing import Any, Dict

from .. import runtime
from ..shared.error_utils import format_error_response
from ..shared.injection_scan import RETRIEVED_TEXT_NOTE, scan_hits

# Citation IDs are 32-character lowercase hex strings (e.g.
# "0de7ea10c59e03dab218a40dece9dffd"), used downstream to build an "id:<x>"
# Lucene lookup (input-validation.md §3c) — reject anything else before it
# reaches the query builder.
_CITATION_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def _pfw_retrieval_guidance(app_number: str, suggested_doc_code: str) -> Dict[str, Any]:
    """Build the pfw_document_retrieval_guidance block returned by
    get_citation_details (audit metrics item 2c: extracted from the inline
    dict literal that used to live in the tool body — content is
    byte-identical to the pre-extraction version)."""
    return {
        "notice": "⚠️ This is citation METADATA only. To get actual documents, use PFW MCP (2-step process):",
        "suggested_document_code": suggested_doc_code,
        "step_1_get_documents": f"pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)",
        "common_citation_documents": {
            "CTNF": "Non-Final Office Action (where this citation most likely appears — start here)",
            "CTFR": "Final Office Action Rejection",
            "NOA": "Notice of Allowance (citation overcame or not used)",
            "892": "Examiner's Search Strategy & Citations List",
            "IDS": "Applicant's Information Disclosure Statement",
        },
        "step_2_options": {
            "for_llm_analysis": f"pfw_get_document_content(app_number='{app_number}', document_identifier='{{from_step_1}}') → Extract text to answer user questions",
            "for_user_download": f"pfw_get_document_download(app_number='{app_number}', document_identifier='{{from_step_1}}') → PDF download link",
        },
        "example_workflow_analysis": f"""
# When user asks "What did the examiner say?" or wants citation context:
docs = pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)
content = pfw_get_document_content(app_number='{app_number}', document_identifier=docs['documents'][0]['documentIdentifier'])
# Analyze content and respond to user question
""",
        "example_workflow_download": f"""
# When user says "Get me the office action" or wants to review themselves:
docs = pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)
download = pfw_get_document_download(app_number='{app_number}', document_identifier=docs['documents'][0]['documentIdentifier'])
# Present as: **📁 [Download Office Action]({{download['proxy_download_url']}})**
""",
        "alternative_xml_retrieval": f"""
# Alternative: Patent XML (rare for citation workflows, use document retrieval above instead)
# If you need patent claims/abstract for prior art comparison:
xml_data = pfw_get_patent_or_application_xml(
    application_number='{app_number}',
    include_fields=['claims', 'abstract'],  # Select only needed fields
    include_raw_xml=False  # ⭐ CRITICAL: 91-99% token reduction (saves ~45KB)
)
# Note: Document retrieval (above) is preferred for citation context and examiner reasoning
""",
    }


async def get_citation_details(
    citation_id: str, include_context: bool = True
) -> Dict[str, Any]:
    """Get complete details for specific citation by ID.

    Use for deep analysis of strategically important citations.
    Full record with all fields and complete citing context.

    ⚠️ IMPORTANT: Returns citation METADATA only, NOT actual documents.

    2-STEP PFW MCP WORKFLOW:
    Step 1: pfw_get_application_documents(app_number='{app_number}', document_code='CTNF', limit=20)

    Document Code Decoder:
    - CTNF: Non-Final Office Action (where most citations appear — start here)
    - CTFR: Final Office Action Rejection
    - NOA: Notice of Allowance
    - 892: Examiner's Search Strategy & Citations List
    - IDS: Applicant's Information Disclosure Statement

    Step 2a (LLM analysis): pfw_get_document_content(app_number, document_identifier) → Extract text for analysis
    Step 2b (User download): pfw_get_document_download(app_number, document_identifier) → PDF download link

    For complete cross-MCP workflows, use citations_get_guidance(section='workflows_pfw') for detailed integration patterns.
    """
    try:
        runtime.initialize_services()
        if not citation_id:
            return format_error_response("Citation ID required", 400)
        if not _CITATION_ID_RE.match(citation_id):
            return format_error_response(
                "Invalid citation_id format (expected a 32-character hex string)",
                400,
            )

        result = await runtime.citation_service.get_details(citation_id, include_context)

        # Add LLM guidance for document retrieval via PFW MCP
        # patentApplicationNumber is nested inside result["citation"], not at the top level
        citation_doc = result.get("citation", {}) if result else {}
        if result and citation_doc.get("patentApplicationNumber"):
            app_number = citation_doc.get("patentApplicationNumber", "")
            oa_category = citation_doc.get("officeActionCategory", "")
            # Map officeActionCategory to PFW document_code
            doc_code_map = {"CTNF": "CTNF", "CTFR": "CTFR"}
            suggested_doc_code = doc_code_map.get(oa_category, "CTNF")
            result["pfw_document_retrieval_guidance"] = _pfw_retrieval_guidance(
                app_number, suggested_doc_code
            )

        # Provenance labeling + detection-only injection scan on the full
        # citation record (kind labels only, key ABSENT when clean; text is
        # never modified).
        if result and "citation" in result:
            result["provenance_note"] = RETRIEVED_TEXT_NOTE
            injection = scan_hits([citation_doc])
            if injection:
                result["injection_scan"] = injection

        return result
    except Exception as e:
        return format_error_response("Details retrieval failed", 500, exception=e)


def register(mcp) -> None:
    """Register get_citation_details (name/schema unchanged)."""
    mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})(get_citation_details)
