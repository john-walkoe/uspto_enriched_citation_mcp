"""Content tests for the four prompt templates that had none.

`test_prompts_gate.py` proves registration is gated on
`CITATIONS_ENABLE_PROMPTS`; `test_enhanced_examiner_prompt_template.py` pins
one template's rendered output. The other four (together about 750 code
lines) had no content assertions at all (T-4). Each is one large f-string, so
the realistic failure is a brace or bracket error at render time, or a stale
tool name left in the prose after a fleet-wide rename — both invisible until
a user runs the prompt.
"""

import pytest

from uspto_enriched_citation_mcp import main as main_module
from uspto_enriched_citation_mcp import prompts


@pytest.fixture(scope="module", autouse=True)
def _enable_prompt_registration():
    """Same reasoning as test_enhanced_examiner_prompt_template.py: force the
    gate and register once; the submodule imports inside register_prompts are
    idempotent through the sys.modules cache."""
    prompts.PROMPTS_ENABLED = True
    prompts.register_prompts(main_module.mcp)


def _fn(module_name, function_name):
    module = getattr(prompts, module_name)
    registered = getattr(module, function_name)
    return registered.fn if hasattr(registered, "fn") else registered


# (module, function, kwargs that exercise the fully-populated branch)
CASES = [
    (
        "patent_citation_analysis",
        "patent_citation_analysis_prompt",
        {"patent_number": "9049188", "include_context": "true"},
    ),
    (
        "technology_citation_landscape_PFW",
        "technology_citation_landscape_PFW_prompt",
        {"technology_keywords": "semiconductor packaging", "tech_center": "2800"},
    ),
    (
        "art_unit_citation_assessment",
        "art_unit_citation_assessment_prompt",
        {"art_unit": "2854"},
    ),
    (
        "litigation_citation_research_PFW_PTAB",
        "litigation_citation_research_PFW_PTAB_prompt",
        {"patent_number": "9049188"},
    ),
]

IDS = [module for module, _, _ in CASES]


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,function_name,kwargs", CASES, ids=IDS)
async def test_prompt_renders_without_a_format_error(
    module_name, function_name, kwargs
):
    body = await _fn(module_name, function_name)(**kwargs)
    assert isinstance(body, str)
    assert len(body) > 500


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,function_name,kwargs", CASES, ids=IDS)
async def test_prompt_renders_with_no_arguments(module_name, function_name, kwargs):
    """Every one of these has an empty/guidance branch; a brace error there
    is exactly as invisible as one on the populated path."""
    body = await _fn(module_name, function_name)()
    assert isinstance(body, str)
    assert body.strip()


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,function_name,kwargs", CASES, ids=IDS)
async def test_prompt_substitutes_its_arguments(module_name, function_name, kwargs):
    body = await _fn(module_name, function_name)(**kwargs)
    for value in kwargs.values():
        if value in ("true", "false"):
            continue
        assert value in body, f"{value!r} missing from the rendered prompt"


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,function_name,kwargs", CASES, ids=IDS)
async def test_prompt_names_only_current_tool_names(
    module_name, function_name, kwargs
):
    """A stale tool name in prompt prose sends the model at a tool that does
    not exist. Every citation tool this repo exposes is Citations_-prefixed
    (the 2026-08 fleet display-name migration)."""
    body = await _fn(module_name, function_name)(**kwargs)

    stale = [
        "search_citations_minimal(",
        "search_citations_balanced(",
        "search_oa_citations_minimal(",
        "get_citation_details(",
        "get_citation_statistics(",
        "PFW_get_document_content(",  # renamed to _with_ocr
    ]
    for name in stale:
        # A bare, unprefixed call is stale; the prefixed form contains it as a
        # substring, so exclude those first.
        occurrences = body.count(name) - body.count("Citations_" + name)
        occurrences -= body.count("PFW_" + name)
        assert occurrences <= 0, f"stale tool reference {name!r} in {module_name}"


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,function_name,kwargs", CASES, ids=IDS)
async def test_prompt_carries_no_ocr_cost_language(module_name, function_name, kwargs):
    """The OCR-cost scrub is a standing content rule for this fleet: per-page
    or per-document dollar costs must not reach a customer-visible string."""
    body = (await _fn(module_name, function_name)(**kwargs)).lower()
    for banned in ("processing_cost_usd", "cost per page", "extraction cost"):
        assert banned not in body
