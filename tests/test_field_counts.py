"""The balanced field count was stated four times and wrong in three.

`config/constants.BALANCED_FIELD_COUNT` said 18, `field_configs.yaml` (the
set actually loaded) held 19, `field_manager.DEFAULT_BALANCED_FIELDS` (the
no-YAML fallback) held 20, and `tools/utility.py` printed "18 comprehensive
fields (20)" to the model in a single self-contradicting string (D-11).

The module-level defaults and the YAML are two copies of the same schema that
could diverge without anything failing, because `_set_default_config` only
runs when the YAML is missing. These assertions are what makes that
divergence fail.
"""

from pathlib import Path

import pytest
import yaml

from uspto_enriched_citation_mcp.config.constants import (
    BALANCED_FIELD_COUNT,
    MINIMAL_FIELD_COUNT,
)
from uspto_enriched_citation_mcp.config.field_manager import (
    DEFAULT_BALANCED_FIELDS,
    DEFAULT_MINIMAL_FIELDS,
)

_YAML = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "field_configs.yaml").read_text()
)
_SETS = _YAML["predefined_sets"]


def test_module_fallback_matches_the_yaml_minimal_set():
    assert DEFAULT_MINIMAL_FIELDS == _SETS["citations_minimal"]["fields"]


def test_module_fallback_matches_the_yaml_balanced_set():
    assert DEFAULT_BALANCED_FIELDS == _SETS["citations_balanced"]["fields"]


def test_the_named_counts_match_the_loaded_sets():
    assert MINIMAL_FIELD_COUNT == len(_SETS["citations_minimal"]["fields"])
    assert BALANCED_FIELD_COUNT == len(_SETS["citations_balanced"]["fields"])


def test_the_balanced_set_omits_fields_the_api_does_not_have():
    """The tool docstring states examinerNameText and firstApplicantName do
    not exist on this API: an examiner query 400s and an applicant query
    silently returns 0. They were in the fallback set anyway."""
    for absent in ("examinerNameText", "firstApplicantName"):
        assert absent not in DEFAULT_BALANCED_FIELDS


@pytest.mark.asyncio
async def test_the_advertised_description_is_derived_not_asserted(mock_runtime):
    from uspto_enriched_citation_mcp.tools.utility import get_available_fields

    mock_runtime.api_client.get_fields.return_value = {"fields": []}
    result = await get_available_fields()

    sets = result["usage_guidance"]["predefined_sets"]
    assert sets["citations_minimal"] == f"{MINIMAL_FIELD_COUNT} essential fields"
    assert sets["citations_balanced"] == (
        f"{BALANCED_FIELD_COUNT} comprehensive fields"
    )
