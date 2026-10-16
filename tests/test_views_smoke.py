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


# ---------------------------------------------------------------------------
# The panel link builder (2026-09-12)
# ---------------------------------------------------------------------------
# `googlePatentsUrl` stripped spaces, commas and slashes only, so an
# identifier written "WO-2010098305-A1" kept its hyphens and its kind code and
# the button opened a 404, and a foreign document was never reachable at all.
# It is now a hand-written mirror of the Python builder, and this is the table
# both sides are held to: Python first (always), then the JavaScript itself
# under node (skipped where node is absent, so the mirror is checked wherever
# a runtime exists rather than nowhere).

PANEL_LINKS = {
    # US shapes keep the `US` prefix and lose the kind code.
    "US-20140248322-A1": "https://patents.google.com/patent/US20140248322",
    "US 2006/0075466 A1": "https://patents.google.com/patent/US20060075466",
    "20060075466": "https://patents.google.com/patent/US20060075466",
    "US 6,848,420 B2": "https://patents.google.com/patent/US6848420",
    "RE38,124": "https://patents.google.com/patent/USRE38124",
    "D456,789": "https://patents.google.com/patent/USD456789",
    "PP12345": "https://patents.google.com/patent/USPP12345",
    # Foreign shapes keep their country code and take no `US` prefix.
    "WO-2010098305-A1": "https://patents.google.com/patent/WO2010098305",
    "DE-102004012346-A1": "https://patents.google.com/patent/DE102004012346",
    "DE 10 2004 012346 A1": "https://patents.google.com/patent/DE102004012346",
    "JP-2001123456-A": "https://patents.google.com/patent/JP2001123456",
    "EP 1 234 567 B1": "https://patents.google.com/patent/EP1234567",
    # The OA lane's raw 892 string writes the name on either side.
    "GOTO K WO-2010098305-A1": "https://patents.google.com/patent/WO2010098305",
    "US-20060075466-A1 KAWAI; TAKESHI": (
        "https://patents.google.com/patent/US20060075466"
    ),
    # No link: the card's empty placeholder, a number too short to be a
    # document, non-patent literature, and an abbreviation that is not a
    # country code.
    "—": None,
    "12345": None,
    'Smith et al., "Widget assembly", J. Chem. 12-19, 2000, pp. 123-145.': None,
    "Kokai No. 2001-123456": None,
    "": None,
}


@pytest.mark.parametrize("identifier,url", sorted(PANEL_LINKS.items()))
def test_python_builder_produces_the_panel_link_table(identifier, url):
    """The table is the Python side's own output, so a change there fails here
    before the two builders can drift apart silently."""
    from uspto_enriched_citation_mcp.util.citation_links import google_patents_url
    from uspto_enriched_citation_mcp.util.reference_key import normalize_reference_key

    assert google_patents_url(normalize_reference_key(identifier)) == url


@pytest.mark.parametrize("name,html", sorted(CARD_VIEWS.items()))
def test_card_views_link_foreign_references_by_country_prefix(name, html):
    """The branch that makes a non-US reference reachable at all. A structural
    check, so it holds with no JavaScript runtime present."""
    assert "function foreignCountryPrefix(" in html
    assert "https://patents.google.com/patent/${encodeURIComponent(key)}" in html
    assert "https://patents.google.com/patent/US${encodeURIComponent(key)}" in html


def test_panel_javascript_builds_the_same_links_as_the_python_builder(tmp_path):
    """The mirror, executed. `SHARED_VIEW_JS` declares functions and constants
    only, so it runs outside a browser as it stands."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the JavaScript mirror cannot be run")

    from uspto_enriched_citation_mcp.ui.views._common import SHARED_VIEW_JS

    script = tmp_path / "panel_links.js"
    script.write_text(
        SHARED_VIEW_JS
        + "\nconst IDS = "
        + json.dumps(list(PANEL_LINKS))
        + ";\nconst out = {};\n"
        "for (const id of IDS) out[id] = googlePatentsUrl(id);\n"
        "console.log(JSON.stringify(out));\n"
    )
    completed = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=True
    )

    assert json.loads(completed.stdout) == PANEL_LINKS
