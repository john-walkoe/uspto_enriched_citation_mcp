"""Enhanced Examiner Behavior Intelligence Prompt

Comprehensive examiner profiling combining prosecution patterns (PFW), citation behavior (Citations),
petition history (FPD), and PTAB challenge correlation for strategic prosecution planning.

This enhanced version includes:
- Robust error handling for missing citation data (pre-2017 OA coverage)
- Statistical significance validation (minimum thresholds)
- Progressive disclosure with user confirmation at key decision points
- Enhanced citation category analysis with strategic interpretations
- FPD integration for quality assessment
- PTAB integration for post-grant risk profiling
- Actionable recommendations based on data patterns
- Complete download workflows and presentation formatting

The bulk of the prompt body lives in
prompts/templates/enhanced_examiner_behavior_intelligence.md and is rendered
with string.Template at call time (see _render_body below). The template was
generated mechanically from the original f-string so the rendered output is
byte-identical; see tests/test_enhanced_examiner_prompt_template.py.
"""

from importlib import resources
from string import Template

from . import mcp

_TEMPLATE_PACKAGE = "uspto_enriched_citation_mcp.prompts.templates"
_TEMPLATE_FILENAME = "enhanced_examiner_behavior_intelligence.md"


def _load_template() -> Template:
    text = (
        resources.files(_TEMPLATE_PACKAGE)
        .joinpath(_TEMPLATE_FILENAME)
        .read_text(encoding="utf-8")
    )
    return Template(text)


def _render_body(examiner_name: str, art_unit: str, technology_keywords: str) -> str:
    """Render the main report body from the template.

    Mirrors the original f-string exactly: the three raw params are
    substituted verbatim where they appeared as `{param}`, and the three
    `_display` values (falling back to "Not specified") are substituted
    where the original had `{param or "Not specified"}`.
    """
    template = _load_template()
    return template.substitute(
        examiner_name=examiner_name,
        art_unit=art_unit,
        technology_keywords=technology_keywords,
        examiner_name_display=examiner_name or "Not specified",
        art_unit_display=art_unit or "Not specified",
        technology_keywords_display=technology_keywords or "Not specified",
    )


@mcp.prompt(
    name="enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD",
    description="ENHANCED: Comprehensive examiner profiling with citation patterns, petition history, PTAB correlation, and strategic prosecution recommendations. At least ONE parameter required (examiner_name, art_unit, or technology_keywords). Citations data Oct 1, 2017+ only. Requires PFW, Citations, FPD, and PTAB MCPs.",
)
async def enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD_prompt(
    examiner_name: str = "", art_unit: str = "", technology_keywords: str = ""
) -> str:
    """Generate comprehensive examiner profiles combining prosecution patterns, citation behavior,
    petition history, and PTAB challenge correlation for strategic prosecution planning.

    MANDATORY FIRST STEP: Validate the provided parameters and immediately begin analysis using
    any non-empty parameter. If ALL parameters are empty, ask the user to provide at least one
    search parameter.

    This is a COMPREHENSIVE MULTI-PHASE workflow:
    1. PFW: Get examiner's applications with wildcard search + ultra-minimal fields
    2. Citations: Analyze citation patterns with 2017+ date filtering
    3. PFW: NOA deep dive for allowance reasoning patterns
    4. PFW: Prosecution efficiency metrics (RCE, finals, amendments)
    5. FPD: Petition history for quality assessment
    6. PTAB: Post-grant challenge correlation
    7. Generate comprehensive intelligence report with strategic recommendations

    Args:
        examiner_name: Examiner last name or full name (e.g., 'SMITH' or 'SMITH, JOHN')
        art_unit: Optional art unit number for filtering (e.g., '2854')
        technology_keywords: Optional technology focus areas
    """

    # Validate inputs
    if not examiner_name and not art_unit and not technology_keywords:
        return """
# ENHANCED EXAMINER BEHAVIOR INTELLIGENCE SYSTEM

❌ **ERROR: Missing Search Parameters**

Please provide at least one search parameter:
- **Examiner Name**: Last name or full name (e.g., 'SMITH' or 'SMITH, JOHN')
- **Art Unit**: Art unit number (e.g., '2854')
- **Technology Keywords**: Technology focus areas

**Example Usage:**
```
examiner_name='MEKHLIN, ELI S'
art_unit='1759'
technology_keywords='semiconductor'
```

**Recommended:** Provide examiner name AND art unit for best results and fastest execution.
"""

    return _render_body(examiner_name, art_unit, technology_keywords)
