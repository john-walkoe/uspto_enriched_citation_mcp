"""S-04: three of four MCP App views interpolated upstream text unescaped.

`user_management_view.py` defined a correct `esc()` and wrapped every value;
the citation-results, OA-citations and statistics views did not. The values
come from api.uspto.gov, but this repo already treats that text as
untrustworthy (`shared/injection_scan.py`, `docs/CONTENT_PROVENANCE.md`), and
`passageLocationText` is AI-extracted from office actions that quote arbitrary
applicant-drafted text.

Structural checks: real rendering is validated manually in Claude Desktop.
"""

import pytest

from uspto_enriched_citation_mcp.ui.views import (
    CITATION_RESULTS_HTML,
    OA_CITATIONS_HTML,
    STATISTICS_HTML,
    USER_MANAGEMENT_HTML,
)

ALL_VIEWS = {
    "citations": CITATION_RESULTS_HTML,
    "oa": OA_CITATIONS_HTML,
    "statistics": STATISTICS_HTML,
    "user-management": USER_MANAGEMENT_HTML,
}


@pytest.mark.parametrize("html", ALL_VIEWS.values(), ids=ALL_VIEWS.keys())
def test_every_view_defines_the_escape_helper(html):
    assert "function esc(s)" in html


@pytest.mark.parametrize(
    "field", ["citedId", "appNum", "artUnit", "techCenter", "oaDate", "inventor"]
)
def test_citation_card_escapes_upstream_fields(field):
    assert f"esc({field})" in CITATION_RESULTS_HTML
    # No bare interpolation anywhere: appNum's one non-HTML use, the Patent
    # Center URL, now goes through encodeURIComponent (S-33), matching what
    # googlePatentsUrl three lines away already did.
    assert CITATION_RESULTS_HTML.count("${" + field + "}") == 0
    if field == "appNum":
        assert (
            "patentcenter.uspto.gov/applications/${encodeURIComponent(appNum)}"
            in CITATION_RESULTS_HTML
        )


def test_citation_card_escapes_passages_and_claim_numbers():
    assert "esc(formatPassages(passages))" in CITATION_RESULTS_HTML
    assert "esc(doc.relatedClaimNumberText)" in CITATION_RESULTS_HTML
    assert "${formatPassages(passages)}" not in CITATION_RESULTS_HTML


def test_citation_filter_pills_escape_their_labels():
    assert "esc(cfg.label || val)" in CITATION_RESULTS_HTML
    assert "esc(label)" in CITATION_RESULTS_HTML


@pytest.mark.parametrize(
    "field", ["refId", "artUnit", "techCenter", "workGroup", "para", "created"]
)
def test_oa_card_escapes_upstream_fields(field):
    assert f"esc({field})" in OA_CITATIONS_HTML
    assert "${" + field + "}" not in OA_CITATIONS_HTML


def test_oa_card_escapes_the_application_number_in_html():
    """appNum is escaped in markup and URL-encoded in the Patent Center link."""
    assert "esc(appNum)" in OA_CITATIONS_HTML
    assert OA_CITATIONS_HTML.count("${appNum}") == 0
    assert (
        "patentcenter.uspto.gov/applications/${encodeURIComponent(appNum)}"
        in OA_CITATIONS_HTML
    )


def test_oa_filter_pills_escape_their_labels():
    assert "esc(displayLabel)" in OA_CITATIONS_HTML


def test_statistics_view_escapes_aggregation_keys_and_title_attributes():
    """Breakdown keys and sample-record values are upstream field values."""
    assert 'title="${esc(label)}"' in STATISTICS_HTML
    assert "${esc(label)}</div>" in STATISTICS_HTML
    assert 'title="${esc(v)}"' in STATISTICS_HTML
    assert "esc(display)" in STATISTICS_HTML
    assert "esc(k)" in STATISTICS_HTML
    assert 'title="${label}"' not in STATISTICS_HTML


def test_statistics_raw_json_fallback_is_escaped():
    assert "esc(JSON.stringify(data, null, 2))" in STATISTICS_HTML
    assert "${JSON.stringify(data, null, 2)}" not in STATISTICS_HTML
