"""Structural guard for the four MCP App HTML constants.

The `ui/views` package is about a thousand lines of HTML, CSS and JavaScript
embedded in Python string constants with no test of any kind: a typo inside
one of them shipped silently, and two of the four were built by copy-and-edit
so a copy error was likely (T-3). `tests/test_csp_domains.py` covers the CSP
domain list that wraps these; nothing covered the constants themselves.
"""

import pytest

from uspto_enriched_citation_mcp.ui.views import (
    CITATION_RESULTS_HTML,
    OA_CITATIONS_HTML,
    STATISTICS_HTML,
    USER_MANAGEMENT_HTML,
)

ALL_VIEWS = {
    "citation_results": CITATION_RESULTS_HTML,
    "oa_citations": OA_CITATIONS_HTML,
    "statistics": STATISTICS_HTML,
    "user_management": USER_MANAGEMENT_HTML,
}

# The two card views built from the same source; the other two are their own
# shape (a chart panel and an admin table).
CARD_VIEWS = {
    "citation_results": CITATION_RESULTS_HTML,
    "oa_citations": OA_CITATIONS_HTML,
}


@pytest.mark.parametrize("name,html", sorted(ALL_VIEWS.items()))
def test_view_is_a_well_formed_app_document(name, html):
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "app.connect()" in html
    assert "app.ontoolresult" in html
    assert html.count("<script") == html.count("</script>")
    assert html.count("<style") == html.count("</style>")


@pytest.mark.parametrize("name,html", sorted(ALL_VIEWS.items()))
def test_view_loads_the_ext_apps_bundle_from_the_csp_allowed_origin(name, html):
    assert "cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps" in html


@pytest.mark.parametrize("name,html", sorted(ALL_VIEWS.items()))
def test_every_view_can_report_an_error(name, html):
    assert "function showError(" in html


@pytest.mark.parametrize("name,html", sorted(ALL_VIEWS.items()))
def test_every_view_escapes_interpolated_values(name, html):
    """All four define the esc() helper; three of them did not, and
    interpolated USPTO-derived text into innerHTML raw (S-04)."""
    assert "function esc(" in html
    assert "esc(" in html


@pytest.mark.parametrize("name,html", sorted(CARD_VIEWS.items()))
def test_card_views_url_encode_the_application_number(name, html):
    """`googlePatentsUrl` three lines away used encodeURIComponent and the
    Patent Center link did not (S-33)."""
    assert (
        "patentcenter.uspto.gov/applications/${encodeURIComponent(appNum)}" in html
    )


@pytest.mark.parametrize("name,html", sorted(CARD_VIEWS.items()))
def test_card_views_share_one_copy_of_the_common_javascript(name, html):
    """The seven duplicated helpers now come from one constant (D-3)."""
    from uspto_enriched_citation_mcp.ui.views._common import SHARED_VIEW_JS

    assert SHARED_VIEW_JS in html
    # And exactly once: an accidental double interpolation would redefine
    # every helper.
    assert html.count("function googlePatentsUrl(") == 1
    assert html.count("function showError(") == 1
    assert html.count("function sep(") == 1
