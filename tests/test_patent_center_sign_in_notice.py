"""Patent Center is only readable signed in, and every surface says so.

A Patent Center link handed to a reader with no USPTO.gov account does not
error: it silently renders the site's own front page. The reader then believes
the citation was wrong. So every surface that hands out such a link carries the
same sentence: the JSON `citation_note` on any response whose rows carry
`application_cite_as` (the balanced tiers, the details tool, and a custom
`fields` list that names it), the full rules in the overview guidance section,
and the two MCP App card panels that render an "Open citing application in
Patent Center" button. Since 2026-09-11 a response whose rows carry Google
Patents links only (the minimal tiers, a plain custom list) serves the short
note without it, because it hands out no Patent Center link.

The sentence is asserted verbatim so a reworded copy in one place cannot drift
away from the other.
"""

import pytest

from uspto_enriched_citation_mcp.ui.views import (
    CITATION_RESULTS_HTML,
    OA_CITATIONS_HTML,
)
from uspto_enriched_citation_mcp.util.citation_links import (
    PATENT_CENTER_SIGN_IN_RULE,
    citation_note,
)

SIGN_IN_SENTENCE = (
    "Patent Center shows an application only to a signed-in reader: without a "
    "free USPTO.gov account the link lands on its own front page rather than "
    "on the desired application."
)

#: The views that render a Patent Center button.
PATENT_CENTER_VIEWS = {
    "citation_results": CITATION_RESULTS_HTML,
    "oa_citations": OA_CITATIONS_HTML,
}


def test_the_envelope_note_carries_the_sign_in_sentence():
    """On every envelope whose rows carry a Patent Center link."""
    note = citation_note(application_links=True)
    assert SIGN_IN_SENTENCE in note
    assert PATENT_CENTER_SIGN_IN_RULE in note
    # No em dashes in new prose (repo rule).
    assert "\u2014" not in PATENT_CENTER_SIGN_IN_RULE


def test_the_overview_guidance_carries_the_sign_in_sentence():
    from uspto_enriched_citation_mcp.config.tool_reflections import (
        _get_overview_section,
    )

    flat = " ".join(_get_overview_section().split())
    assert SIGN_IN_SENTENCE in flat


def test_the_rule_tells_the_model_what_to_do_with_each_target():
    assert "application_cite_as" in PATENT_CENTER_SIGN_IN_RULE
    assert "patentcenter.uspto.gov" in PATENT_CENTER_SIGN_IN_RULE
    assert "Google Patents" in PATENT_CENTER_SIGN_IN_RULE
    assert "no account" in PATENT_CENTER_SIGN_IN_RULE


@pytest.mark.parametrize(
    "html", PATENT_CENTER_VIEWS.values(), ids=PATENT_CENTER_VIEWS.keys()
)
def test_every_patent_center_view_shows_the_notice(html):
    assert SIGN_IN_SENTENCE in html
    assert 'class="pc-note"' in html
    assert ".pc-note {" in html


@pytest.mark.parametrize(
    "html", PATENT_CENTER_VIEWS.values(), ids=PATENT_CENTER_VIEWS.keys()
)
def test_the_existing_button_text_is_untouched(html):
    assert "Open citing application in Patent Center →" in html
