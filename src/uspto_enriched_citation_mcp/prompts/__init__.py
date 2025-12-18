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
"""

# Global mcp object set by register_prompts()
mcp = None


def register_prompts(mcp_server):
    """Register all prompt templates with the MCP server.

    This function must be called after the MCP server is initialized.
    It sets the global mcp object and imports all prompt modules,
    which then register their prompts using the @mcp.prompt() decorator.

    Args:
        mcp_server: The initialized FastMCP server instance
    """
    global mcp
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
