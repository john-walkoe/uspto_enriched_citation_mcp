"""`examinerCitedReferenceIndicator` is a JSON boolean, not the string "true".

Every prompt in this server emitted analysis code that compared the field to
the string `'true'`. It never matches, so every run reported 100 percent
applicant-cited references - the exact opposite of the truth on an
examiner-cited row, and load-bearing in the invalidity and examiner-behavior
prompts. Confirmed live 2026-09-04: the field returns as a JSON boolean in
every sampled record on both lanes.

These tests pin the emitted predicate against a boolean `True` row and refuse
the string comparison anywhere in the prompt surface.
"""

import re
from pathlib import Path

import pytest

from uspto_enriched_citation_mcp import main as main_module
from uspto_enriched_citation_mcp import prompts

_PROMPTS_DIR = Path(prompts.__file__).resolve().parent


@pytest.fixture(scope="module", autouse=True)
def _enable_prompt_registration():
    """Same reasoning as tests/test_prompt_content.py: force the gate and
    register once so the prompt submodules are importable as attributes."""
    prompts.PROMPTS_ENABLED = True
    prompts.register_prompts(main_module.mcp)


def _fn(module_name, function_name):
    module = getattr(prompts, module_name)
    registered = getattr(module, function_name)
    return registered.fn if hasattr(registered, "fn") else registered

#: The comparison that was shipped, in any quoting style.
_STRING_COMPARISON = re.compile(
    r"""\.get\(\s*['"]examinerCitedReferenceIndicator['"]\s*\)\s*==\s*['"]true['"]"""
)

#: What every site emits now: read the value as text first, so a JSON boolean
#: True and a string "true" both count as examiner-cited.
_BOOLEAN_TOLERANT = re.compile(
    r"""str\(\s*\w+\.get\(\s*['"]examinerCitedReferenceIndicator['"]\s*\)\s*\)"""
    r"""\.lower\(\)\s*==\s*['"]true['"]"""
)


def _prompt_sources():
    """Every prompt source and template that can carry the comparison."""
    return sorted(
        p
        for p in _PROMPTS_DIR.rglob("*")
        if p.suffix in {".py", ".md"} and "__pycache__" not in p.parts
    )


def _examiner_cited(citation):
    """The predicate the prompts emit, evaluated here so the tests exercise the
    same expression the model is told to run."""
    return str(citation.get("examinerCitedReferenceIndicator")).lower() == "true"


class TestEmittedPredicate:
    def test_boolean_true_row_is_examiner_cited(self):
        """The row the shipped code got wrong."""
        assert _examiner_cited({"examinerCitedReferenceIndicator": True}) is True

    def test_boolean_false_row_is_applicant_cited(self):
        assert _examiner_cited({"examinerCitedReferenceIndicator": False}) is False

    def test_missing_and_null_are_not_examiner_cited(self):
        assert _examiner_cited({}) is False
        assert _examiner_cited({"examinerCitedReferenceIndicator": None}) is False

    def test_a_string_true_still_counts(self):
        """Boolean-tolerant, not boolean-only: an upstream shape change to a
        string must not silently flip the answer back."""
        assert _examiner_cited({"examinerCitedReferenceIndicator": "true"}) is True
        assert _examiner_cited({"examinerCitedReferenceIndicator": "True"}) is True

    def test_the_shipped_comparison_would_have_failed_this(self):
        """States the defect, so a future edit that reintroduces it fails a
        test that says why."""
        row = {"examinerCitedReferenceIndicator": True}
        assert row.get("examinerCitedReferenceIndicator") != "true"


class TestPromptSources:
    def test_no_prompt_compares_the_indicator_to_a_string(self):
        offenders = [
            str(p.relative_to(_PROMPTS_DIR))
            for p in _prompt_sources()
            if _STRING_COMPARISON.search(p.read_text(encoding="utf-8"))
        ]
        assert offenders == []

    def test_every_comparison_site_is_boolean_tolerant(self):
        """Seven sites across four files as of 2026-09-04; the count is a
        ratchet so a new prompt cannot quietly add an eighth wrong one."""
        sites = sum(
            len(_BOOLEAN_TOLERANT.findall(p.read_text(encoding="utf-8")))
            for p in _prompt_sources()
        )
        assert sites == 7

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "module_name,function_name,kwargs",
        [
            (
                "patent_citation_analysis",
                "patent_citation_analysis_prompt",
                {"patent_number": "9049188"},
            ),
            (
                "art_unit_citation_assessment",
                "art_unit_citation_assessment_prompt",
                {"art_unit": "2854"},
            ),
            (
                "litigation_citation_research_PFW_PTAB",
                "litigation_citation_research_PFW_PTAB_prompt",
                {"patent_number": "7971071"},
            ),
        ],
    )
    async def test_rendered_prompts_carry_the_fixed_predicate(
        self, module_name, function_name, kwargs
    ):
        """The rendered text is what the model actually receives, so the fix
        has to survive f-string interpolation, not just live in the source."""
        text = await _fn(module_name, function_name)(**kwargs)
        assert not _STRING_COMPARISON.search(text)
        assert _BOOLEAN_TOLERANT.search(text)
