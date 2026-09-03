"""
Tool reflections and LLM guidance for USPTO Enriched Citation MCP.

This module provides sectioned guidance for context-efficient access.
Content is loaded from reference/tool_guidance.md at runtime.

Editing reference/tool_guidance.md updates guidance without touching Python code.
"""

import re
from pathlib import Path
from typing import Dict

from ..util.logging import get_logger

_logger = get_logger(__name__)

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

    # Log-only injection scan over the loaded guidance (S-42). This is a
    # deliberate content-team seam and the trust assumption is correct as
    # designed — but it is a DIRECT model-instruction channel with no runtime
    # check, while a lower-privilege channel (quoted USPTO text) has one.
    # `.security/check_prompt_injections.py` covers it at commit time; this
    # catches content that reaches the image without passing through a commit.
    # Nothing is stripped or rewritten: a hit is a signal to a human.
    try:
        from ..shared.injection_scan import scan_text

        for section_name, section_body in _SECTION_MAP.items():
            kinds = scan_text(section_body)
            if kinds:
                _logger.warning(
                    "Guidance section '%s' matched injection patterns %s; "
                    "content served unchanged, review reference/tool_guidance.md",
                    section_name,
                    sorted(kinds),
                )
    except Exception as scan_error:  # pragma: no cover - scanning is advisory
        _logger.debug(
            "Guidance injection scan unavailable: %s", type(scan_error).__name__
        )

except Exception as exc:
    _logger.warning(
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


def _get_oa_citations_section() -> str:
    return _SECTION_MAP.get("oa_citations", "")


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
        "For 90-95% token reduction, use `Citations_get_guidance(section)` instead.\n\n"
        "Use `Citations_get_guidance(\"overview\")` to see available sections and quick reference chart.\n\n"
        + _get_overview_section()
    )
