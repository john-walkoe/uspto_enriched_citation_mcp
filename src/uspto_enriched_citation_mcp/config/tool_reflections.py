"""
Tool reflections and LLM guidance for USPTO Enriched Citation MCP.

This module provides sectioned guidance for context-efficient access.
Content is loaded from reference/tool_guidance.md at runtime.

Editing reference/tool_guidance.md updates guidance without touching Python code.
"""

import re
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# Content loading
# ---------------------------------------------------------------------------

_REFERENCE_DIR = Path(__file__).parent.parent.parent.parent / "reference"
_REFERENCE_FILE = _REFERENCE_DIR / "tool_guidance.md"

# Loaded once at import time; content team edits the .md file instead of Python
_SECTION_MAP: Dict[str, str] = {}

try:
    raw = _REFERENCE_FILE.read_text(encoding="utf-8")

    # File format: each section is "## name\n\ncontent\n\n"
    # Regex captures section name (group 1) and body (group 2).
    # The \n\n before ## must not be consumed so it stays with the previous body.
    pattern = re.compile(r"(?:^|\n)## ([a-z_]+)\n\n(.*?)(?=\n## [a-z_]+\n\n|$)", re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(raw):
        section_name = match.group(1).strip().lower()
        section_body = match.group(2)
        _SECTION_MAP[section_name] = section_body

except Exception as exc:
    import logging
    logging.getLogger(__name__).warning(
        "Could not load tool_guidance.md (%s): guidance strings unavailable", exc
    )


# ---------------------------------------------------------------------------
# Section accessors (same signatures as before — backward-compatible)
# ---------------------------------------------------------------------------

def _get_overview_section() -> str:
    return _SECTION_MAP.get("overview", "")


def _get_tools_section() -> str:
    return _SECTION_MAP.get("tools", "")


def _get_workflows_pfw_section() -> str:
    return _SECTION_MAP.get("workflows_pfw", "")


def _get_workflows_ptab_section() -> str:
    return _SECTION_MAP.get("workflows_ptab", "")


def _get_workflows_fpd_section() -> str:
    return _SECTION_MAP.get("workflows_fpd", "")


def _get_workflows_complete_section() -> str:
    return _SECTION_MAP.get("workflows_complete", "")


def _get_citation_codes_section() -> str:
    return _SECTION_MAP.get("citation_codes", "")


def _get_data_coverage_section() -> str:
    return _SECTION_MAP.get("data_coverage", "")


def _get_fields_section() -> str:
    return _SECTION_MAP.get("fields", "")


def _get_errors_section() -> str:
    return _SECTION_MAP.get("errors", "")


def _get_cost_section() -> str:
    return _SECTION_MAP.get("cost", "")


def get_all_reflections() -> str:
    """Get all tool reflections and guidance (legacy compatibility)."""
    return (
        "# USPTO Enriched Citation API v3 - Complete Tool Guidance\n\n"
        "⚠️ **DEPRECATION NOTICE**: This function returns all guidance at once (~62KB).\n"
        "For 90-95% token reduction, use `citations_get_guidance(section)` instead.\n\n"
        "Use `citations_get_guidance(\"overview\")` to see available sections and quick reference chart.\n\n"
        + _get_overview_section()
    )


def get_tool_reflections(workflow_type: str = "general") -> str:
    """
    Legacy function for backward compatibility.

    ⚠️ **DEPRECATED**: Use citations_get_guidance(section) instead.

    This function provides workflow-based guidance but is less efficient than
    the sectioned approach. New code should use citations_get_guidance().
    """
    workflow_map = {
        "cross_mcp":   "workflows_complete",
        "litigation":  "workflows_complete",
        "prosecution": "workflows_pfw",
        "portfolio":    "workflows_complete",
        "general":      "overview",
    }
    section = workflow_map.get(workflow_type, "overview")

    return (
        "# USPTO Enriched Citation MCP - Workflow Guidance\n\n"
        "⚠️ **DEPRECATION NOTICE**: get_tool_reflections() is deprecated.\n"
        f'Use `citations_get_guidance("{section}")` for better context efficiency.\n\n'
        f"{_get_overview_section()}"
    )
