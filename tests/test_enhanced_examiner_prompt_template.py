"""Regression test for the enhanced_examiner_behavior_intelligence prompt
template extraction (Phase 6A audit item 8).

The prompt's ~1500-line f-string body was moved verbatim into
prompts/templates/enhanced_examiner_behavior_intelligence.md and is now
rendered at call time via string.Template. The render is fully static text
substitution (no dates, randomness, or I/O beyond reading the bundled
template file), so it is deterministic — the sha256 anchors below were
computed from the ORIGINAL f-string implementation before the refactor and
must still match byte-for-byte after it.
"""

import hashlib

import pytest

from uspto_enriched_citation_mcp import main as main_module
from uspto_enriched_citation_mcp import prompts

# sha256 of the rendered output from the pre-refactor f-string implementation,
# for three fixed argument sets. Do not update these unless the intentional
# prompt CONTENT is changing — a mismatch here means the refactor altered
# what the LLM sees, which is exactly what this test guards against.
_EXPECTED_SHA256 = {
    "full": "557a102795ed2def01d4e44d936be9fc738b0ab2bd8a0e718231efe32e840eb6",
    "empty": "5483d7b477e5081a5b84c0ab1ce4370cd9ae14e200eb607baad415b097a2c10f",
    "examiner_only": "cc8df79ba13d9c2c7dab47fe3accda6186300bc89125df4b57bd844a964c9fa3",
}

_CASES = {
    "full": dict(
        examiner_name="SMITH, JOHN", art_unit="1759", technology_keywords="semiconductor"
    ),
    "empty": dict(),
    "examiner_only": dict(examiner_name="MEKHLIN, ELI S"),
}


@pytest.fixture(scope="module")
def prompt_fn():
    """The underlying (undecorated) async prompt function.

    Importing `main` (above) already triggers register_prompts(main.mcp) —
    the @mcp.prompt(...) decorator only runs on first import of this
    submodule (Python caches modules in sys.modules), so we deliberately
    don't create a second throwaway FastMCP instance and re-register here;
    that would silently no-op if another test module already imported
    `main` first, and only the original registration's function object
    would be reachable anyway.
    """
    registered = (
        prompts.enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD
        .enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD_prompt
    )
    return registered.fn if hasattr(registered, "fn") else registered


class TestPromptRenderRegression:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("case_name", sorted(_CASES))
    async def test_render_matches_pre_refactor_sha256(self, prompt_fn, case_name):
        result = await prompt_fn(**_CASES[case_name])
        actual = hashlib.sha256(result.encode("utf-8")).hexdigest()
        assert actual == _EXPECTED_SHA256[case_name], (
            f"Rendered output for case {case_name!r} changed vs. the "
            f"pre-refactor f-string implementation (sha256 mismatch)."
        )

    @pytest.mark.asyncio
    async def test_full_render_contains_all_three_params(self, prompt_fn):
        result = await prompt_fn(
            examiner_name="DOE, JANE", art_unit="2854", technology_keywords="battery"
        )
        assert "DOE, JANE" in result
        assert "2854" in result
        assert "battery" in result

    @pytest.mark.asyncio
    async def test_missing_params_display_as_not_specified(self, prompt_fn):
        result = await prompt_fn(examiner_name="ONLY NAME")
        assert "**Art Unit**: Not specified" in result
        assert "**Technology Focus**: Not specified" in result
        assert "**Examiner**: ONLY NAME" in result


class TestPromptRegistration:
    """The @mcp.prompt registration metadata must be untouched by the
    template extraction."""

    @pytest.mark.asyncio
    async def test_registered_name_and_description_unchanged(self):
        registered_prompts = await main_module.mcp.list_prompts()
        matches = [
            p
            for p in registered_prompts
            if p.name == "enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD"
        ]
        assert len(matches) == 1
        prompt = matches[0]
        assert prompt.description == (
            "ENHANCED: Comprehensive examiner profiling with citation patterns, "
            "petition history, PTAB correlation, and strategic prosecution "
            "recommendations. At least ONE parameter required (examiner_name, "
            "art_unit, or technology_keywords). Citations data Oct 1, 2017+ only. "
            "Requires PFW, Citations, FPD, and PTAB MCPs."
        )
        arg_names = {a.name for a in (prompt.arguments or [])}
        assert arg_names == {"examiner_name", "art_unit", "technology_keywords"}
