"""
Citations MCP Prompt Templates

This module contains comprehensive prompt templates for USPTO Enriched Citation analysis workflows.
Each prompt provides complete implementation guidance with working code, error handling, safety rails,
and cross-MCP integration patterns (PFW, PTAB, FPD).

All prompts follow the comprehensive implementation pattern:
- Complete working code with loops and data processing
- Error handling with try/except for cross-MCP calls
- Safety rails with explicit context limits
- Presentation formatting with markdown tables
- Result aggregation and scoring systems
- Cross-MCP integration workflows

Available Prompts:
- enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD: ENHANCED examiner profiling with citations, petitions, PTAB correlation
- technology_citation_landscape_PFW: Technology area prior art mapping
- patent_citation_analysis: Complete patent/application citation analysis
- art_unit_citation_assessment: Art unit citation norms and examiner patterns
- litigation_citation_research_PFW_PTAB: Comprehensive litigation research package

Registration-gated by CITATIONS_ENABLE_PROMPTS (default off — matches the
CITATIONS_ENABLE_USER_MANAGEMENT pattern: filtered at registration time, so
the prompts never appear in prompts/list when off).
"""

import os

from ..util.logging import get_logger

logger = get_logger(__name__)

# Registration gate for the prompt templates (same pattern as
# CITATIONS_ENABLE_USER_MANAGEMENT in tools/admin.py). Default OFF: prompts
# are opt-in server-side.
PROMPTS_ENABLED = (
    os.getenv("CITATIONS_ENABLE_PROMPTS", "false").lower() == "true"
)

# Global mcp object set by register_prompts()
mcp = None


def register_prompts(mcp_server):
    """Register all prompt templates with the MCP server.

    This function must be called after the MCP server is initialized.
    It sets the global mcp object and imports all prompt modules,
    which then register their prompts using the @mcp.prompt() decorator.

    No-op unless CITATIONS_ENABLE_PROMPTS=true (default off), so no prompts
    are registered on the server by default.

    Args:
        mcp_server: The initialized FastMCP server instance
    """
    global mcp

    if not PROMPTS_ENABLED:
        logger.info(
            "Prompt templates not registered (CITATIONS_ENABLE_PROMPTS is "
            "off; default)."
        )
        return

    mcp = mcp_server

    # Import all prompt modules to register them with the MCP server
    # These imports must happen AFTER mcp is set
    from . import enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD  # noqa: F401
    from . import technology_citation_landscape_PFW  # noqa: F401
    from . import patent_citation_analysis  # noqa: F401
    from . import art_unit_citation_assessment  # noqa: F401
    from . import litigation_citation_research_PFW_PTAB  # noqa: F401


__all__ = [
    'register_prompts',
    'enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD',
    'technology_citation_landscape_PFW',
    'patent_citation_analysis',
    'art_unit_citation_assessment',
    'litigation_citation_research_PFW_PTAB',
]
