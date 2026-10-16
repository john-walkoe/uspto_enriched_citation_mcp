"""Ready-made citation links for every citation record.

A walkthrough of the suite (2026-09-05) ended with three references named in
prose as bare numbers, because that is all the record JSON carried: the MCP App
panels build Google Patents and Patent Center links in the browser, and the
JSON return paths the model actually reads carried none. A number a reader
cannot click is not a citation.

Each citation record therefore carries two derived link keys:

    cite_as              the CITED REFERENCE, on Google Patents
    application_cite_as  the APPLICATION the office action belongs to,
                         on Patent Center

Both are ready-made markdown links, so an answer can paste one after a sentence
without the model assembling a URL of its own. Where a key is served it is
`None` when this server cannot build a VERIFIED public URL for the row: the
same discipline `referenceKey` follows (util/reference_key), and for the same
reason. A null states that this particular reference has no linkable public
record here.

NARROW REQUESTS (2026-09-11). The minimal tiers and any custom `fields` list
are the narrow shapes, and there each row carries ONE link field, `cite_as`,
in the compact form: the verified URL as a markdown autolink (the URL between
angle brackets), with no label. `application_cite_as` rides on a narrow row
only when a custom `fields` list names it, and so does `referenceKey` (the
default minimal tiers keep `referenceKey`, the cross-lane join key). The
balanced tiers and the details tool keep both labelled links. Measured on app
16816197 before this: the OA minimal tier went 5,970 -> 11,658 characters and
a two-field custom list 5,914 -> 13,834 once every row carried two labelled
links, `referenceKey` and a 1,436-character envelope note, so a request for
two fields came back with six per row.

KEY SHAPES. `cite_as` is built from the row's `referenceKey`, which is already
normalised (uppercase, leading `US` and kind code stripped, separators
removed). The shape of that key is what says which document it names:

    11 digits        pre-grant publication   20010056539 -> US 2001/0056539
    7 or 8 digits    granted patent          6694384     -> US 6,694,384
    RE / D / PP + digits   reissue, design, plant patent
    CC + 5 to 13 digits    foreign document  JP2001123456 -> JP 2001123456

Anything else gets NO link: non-patent literature (a `referenceKey` of `None`),
a 5 or 6 digit key that could be a 19th-century patent or could be a page
number out of a journal citation. Guessing a URL for those would produce a link
that looks authoritative and points at the wrong document, or at nothing.

URL PATTERNS, probed live 2026-09-05 with
`curl -s -o /dev/null -w "%{http_code}" -L <url>`:

    https://patents.google.com/patent/US6694384         200
    https://patents.google.com/patent/US20010056539     200
    https://patents.google.com/patent/USRE38124         200
    https://patents.google.com/patent/USD456789         200
    https://patents.google.com/patent/USPP12345         200
    https://patentcenter.uspto.gov/applications/11752072  200

FOREIGN REFERENCES (2026-09-12). A non-US key used to get no link, and before
util/reference_key kept the country prefix it got a WRONG one: the enriched
lane's bare-digit `publicationNumber` outranked `citedDocumentIdentifier`, so
"DE 10 2004 012345 A1" keyed as `102004012345` and `cite_as` pointed at
https://patents.google.com/patent/US102004012345, a different document in a
different country. Google Patents serves the foreign document itself at
/patent/<CC><digits>, probed on 2026-09-12 with the same
`curl -s -o /dev/null -w "%{http_code}" -L <url>`:

    https://patents.google.com/patent/JP2001123456     200
    https://patents.google.com/patent/EP1234567        200
    https://patents.google.com/patent/WO2010012345     200
    https://patents.google.com/patent/KR20100012345    200
    https://patents.google.com/patent/CN101234567      200
    https://patents.google.com/patent/DE102005001234   200
    https://patents.google.com/patent/DE102004012346   200
    https://patents.google.com/patent/DE19834123       200

And the three WO references on the recorded page for app 16816197, the rows
that made this defect measurable (tests/fixtures, 6 of 33 enriched rows and 5
of 18 OA rows), each against the US form of the same digits:

    https://patents.google.com/patent/WO2010098305     200
    https://patents.google.com/patent/WO2018014120     200
    https://patents.google.com/patent/WO2018164436     200
    https://patents.google.com/patent/US2010098305     404
    https://patents.google.com/patent/US2018164436     404

Controls in that run: `DE999999999999`, `JP9999999999`, `XX1234567` and
`ZZ2001123456` all 404. NO kind code is appended to a foreign URL either, and
the same run says why: `EP1234567B1` is a 200 but `EP1234567A1` is a 404, and
`WO2010012345A9` is a 404 where the bare `WO2010012345` is a 200, so the kind
code a reference was written with is not reliably the one Google Patents
indexes while the bare number resolved for every country probed. (Both
`DE102004012345` and `DE102004012345A1` are 404s: that document does not
exist, and its neighbour `DE102004012346` is a 200.)

Controls in the 2026-09-05 run: `USZZ999999999` and `US99999999` both 404, so a
200 from Google Patents means the document exists rather than an app shell
answering everything. `https://patents.google.com/patent/USRE38124E` (the same
reissue WITH its kind code) is a 404, which is why no kind code is ever
appended: the normalised key has none and none is added back. Patent Center
answers 200 for an application serial that does not exist, so it is not a
liveness check; the pattern is the one the product's own MCP App panels already
open (ui/views/citation_results_view.py), and the 8-digit shape is enforced
here instead.
"""

import re
from typing import Any, List, Optional, Sequence, Tuple

from .reference_key import foreign_country_prefix, normalize_reference_key

#: Record key carrying the cited reference's markdown link (None when the
#: reference has no verified public URL).
CITE_AS_FIELD = "cite_as"

#: Record key carrying the application's markdown link (None when the record
#: carries no 8-digit application serial).
APPLICATION_CITE_AS_FIELD = "application_cite_as"

#: Patent Center is not a public page: it renders an application only to a
#: signed-in reader. A reader handed a bare patentcenter.uspto.gov link with no
#: account lands on the site's own front page and concludes the citation was
#: wrong, so the note that hands out `application_cite_as` says so, and says
#: that Google Patents carries no such condition.
PATENT_CENTER_SIGN_IN_RULE = (
    " Patent Center shows an application only to a signed-in reader: without a "
    "free USPTO.gov account the link lands on its own front page rather than on "
    "the desired application. So whenever you paste an `application_cite_as`, "
    "or any other cite_as whose target is patentcenter.uspto.gov, say in the "
    "same breath that opening it needs a free USPTO.gov account; the Google "
    "Patents target of `cite_as` needs no account and needs no such warning."
)

#: Envelope note for every tool that returns citation records. A few
#: sentences, because it rides on every response; the full rules are the
#: overview section of Citations_get_guidance (reference/tool_guidance.md).
CITATION_NOTE = (
    "CITATIONS ARE LINKS. Paste a row's cite_as after any sentence that relies "
    "on that reference; a bare number is not a citation. A null cite_as means "
    "no verified public link exists (non-patent literature): say so, and never "
    "build a URL yourself. Full rules: "
    "Citations_get_guidance(section='overview')."
)


def citation_note(application_links: bool) -> str:
    """The envelope note for a response. When its rows carry
    `application_cite_as` (a Patent Center target) the sign-in rule rides
    along, since that is the one link that needs a warning; a response with
    Google Patents links only does not carry it."""
    return CITATION_NOTE + (PATENT_CENTER_SIGN_IN_RULE if application_links else "")


#: Envelope note for the statistics tool, which returns counts and no records.
STATISTICS_CITATION_NOTE = (
    "CITATIONS ARE LINKS. This tool returns aggregate counts, so it carries "
    "no per-record `cite_as`: a count is not a citation and cannot be linked "
    "to a public record. To cite any of the citations behind a number here, "
    "re-run the same criteria through Citations_search_citations_minimal or "
    "Citations_search_oa_citations_minimal, whose rows each carry a "
    "ready-made `cite_as` link."
)

# --- URL builders -----------------------------------------------------------

_GOOGLE_PATENTS_TEMPLATE = "https://patents.google.com/patent/US{doc}"
# A foreign key already carries its country code, so no prefix is added.
_GOOGLE_PATENTS_FOREIGN_TEMPLATE = "https://patents.google.com/patent/{doc}"
_PATENT_CENTER_TEMPLATE = "https://patentcenter.uspto.gov/applications/{app}"

# An 11-digit key is a pre-grant publication number: YYYY + 7 serial digits.
_PUBLICATION_KEY = re.compile(r"^(\d{4})(\d{7})$")
# A 7 or 8 digit key is a granted utility patent number.
_PATENT_KEY = re.compile(r"^\d{7,8}$")
# Series-marked keys keep their marker through normalisation. Bounded digit
# counts so a marker glued to a long number cannot produce a plausible-looking
# URL for a document that is not one of these series.
_SERIES_KEY = re.compile(r"^(?:RE\d{5,6}|D\d{5,7}|PP\d{4,6})$")
# Patent Center takes the 8-digit application serial, the shape this product's
# own panels already open.
_APPLICATION_NUMBER = re.compile(r"^\d{8}$")

# Longest name fragment kept in a label. A label is a citation, not a record.
_MAX_NAME_CHARS = 40

# How many leading whitespace tokens of a raw Form 892 string can hold the
# reference number, matching util/reference_key's own prefix window.
_MAX_PREFIX_TOKENS = 3

#: Fields that can carry a person or company name for the cited reference,
#: best first. `inventorNameText` is the enriched (v3) lane's own field;
#: `referenceIdentifier` is the OA (v2) lane's raw Form 892 string, which puts
#: the inventor name after the reference number.
NAME_SOURCE_FIELDS: Sequence[str] = ("inventorNameText", "referenceIdentifier")

#: Field carrying the application serial on both lanes.
APPLICATION_NUMBER_FIELD = "patentApplicationNumber"


def google_patents_url(reference_key: Optional[str]) -> Optional[str]:
    """The Google Patents URL for a normalised `referenceKey`, or None.

    A US key gets the `US<key>` form; a key with a non-US country prefix gets
    the `<CC><digits>` form Google Patents serves foreign documents at (module
    docstring, FOREIGN REFERENCES). None whenever the key is neither of those
    shapes, non-patent literature included, whose key is None to begin with.
    """
    if not reference_key:
        return None
    key = str(reference_key).strip().upper()
    if _PUBLICATION_KEY.match(key) or _PATENT_KEY.match(key) or _SERIES_KEY.match(key):
        return _GOOGLE_PATENTS_TEMPLATE.format(doc=key)
    if foreign_country_prefix(key):
        return _GOOGLE_PATENTS_FOREIGN_TEMPLATE.format(doc=key)
    return None


def patent_center_url(application_number: Any) -> Optional[str]:
    """The Patent Center URL for an application serial, or None when the value
    is not the 8-digit serial the pattern takes."""
    if application_number is None or isinstance(application_number, bool):
        return None
    app = re.sub(r"[\s,/-]", "", str(application_number).strip())
    if not _APPLICATION_NUMBER.match(app):
        return None
    return _PATENT_CENTER_TEMPLATE.format(app=app)


def cite_as_link(label: Optional[str], url: Optional[str]) -> Optional[str]:
    """A markdown citation link, or None without a URL. Square brackets in the
    label would end the link text early, so they are replaced."""
    if not url:
        return None
    text = " ".join(str(label or "source").split()).replace("[", "(").replace("]", ")")
    return f"[{text}]({url})"


def autolink(url: Optional[str]) -> Optional[str]:
    """The compact form: a markdown autolink (the URL between angle brackets)
    whose visible text is the verified URL itself, or None without a URL."""
    if not url:
        return None
    return f"<{url}>"


# --- which shape a request gets ----------------------------------------------


def is_narrow(tier: str, custom_fields: Optional[Sequence[str]]) -> bool:
    """True for the narrow shapes: a minimal tier, or any custom `fields`
    list. Their rows carry the compact `cite_as` (module docstring)."""
    return custom_fields is not None or tier == "minimal"


def wants_application_link(tier: str, custom_fields: Optional[Sequence[str]]) -> bool:
    """Whether rows carry `application_cite_as`: on a custom `fields` list only
    when the list names it, otherwise on every tier but minimal."""
    if custom_fields is not None:
        return APPLICATION_CITE_AS_FIELD in custom_fields
    return tier != "minimal"


# --- label parts ------------------------------------------------------------


def reference_display_number(reference_key: Optional[str]) -> Optional[str]:
    """How a normalised key is written in a label: `US 2001/0056539` for a
    publication, `US 6,694,384` for a patent, `US RE38124` for a series-marked
    one, `DE 102004012345` for a foreign one. None for a key this server does
    not link, which keeps this in step with `google_patents_url`: a row with a
    URL and no display number would be labelled "source"."""
    if not reference_key:
        return None
    key = str(reference_key).strip().upper()
    publication = _PUBLICATION_KEY.match(key)
    if publication:
        return f"US {publication.group(1)}/{publication.group(2)}"
    if _PATENT_KEY.match(key):
        return f"US {int(key):,}"
    if _SERIES_KEY.match(key):
        return f"US {key}"
    country = foreign_country_prefix(key)
    if country:
        return f"{country} {key[len(country):]}"
    return None


def _first_text(value: Any) -> Optional[str]:
    """One field value as text; the first usable entry of a multivalued one."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return None
    text = str(value).strip()
    return text or None


def _short_name(text: Optional[str]) -> Optional[str]:
    """The leading name component of a name string, or None.

    USPTO writes these as `KAWAI; TAKESHI` or `PAVLIN; DENNIS J.`, so the part
    before the first separator is the surname or the company. Nothing is
    rewritten or recased: the label quotes what the record says.
    """
    if not text:
        return None
    head = re.split(r"[;,]", text, maxsplit=1)[0].strip(" .")
    head = re.sub(r"\bet\s+al\.?$", "", head, flags=re.IGNORECASE).strip(" .")
    if not head or head.isdigit():
        return None
    return head[:_MAX_NAME_CHARS].strip()


def _name_after_reference(raw: str, reference_key: str) -> Optional[str]:
    """The name trailing a raw Form 892 string, e.g. `US-20060075466-A1 KAWAI;
    TAKESHI` -> `KAWAI`. None when the string is only the number, or when its
    leading tokens do not reduce to this row's key (in which case whatever
    follows is not reliably a name)."""
    tokens = raw.split()
    for n in range(1, _MAX_PREFIX_TOKENS + 1):
        if normalize_reference_key(" ".join(tokens[:n])) == reference_key:
            return _short_name(" ".join(tokens[n:]))
    return None


def reference_name(doc: Any, reference_key: Optional[str]) -> Optional[str]:
    """The name to lead a cited reference's label with, or None when the
    record carries none."""
    if not isinstance(doc, dict):
        return None
    for field in NAME_SOURCE_FIELDS:
        text = _first_text(doc.get(field))
        if not text:
            continue
        name = (
            _name_after_reference(text, reference_key)
            if field == "referenceIdentifier" and reference_key
            else _short_name(text)
        )
        if name:
            return name
    return None


# --- attachment -------------------------------------------------------------

#: One record's (cite_as, application_cite_as) pair.
CitationLinks = Tuple[Optional[str], Optional[str]]


def citation_links_for_doc(
    doc: Any, reference_key: Optional[str], *, compact: bool = False
) -> CitationLinks:
    """Both links for one citation record. `compact=True` is the narrow
    shapes' autolink form (module docstring, NARROW REQUESTS)."""
    if not isinstance(doc, dict):
        return None, None
    app_number = _first_text(doc.get(APPLICATION_NUMBER_FIELD))
    if compact:
        return (
            autolink(google_patents_url(reference_key)),
            autolink(patent_center_url(app_number)),
        )
    number = reference_display_number(reference_key)
    label = number
    if number:
        name = reference_name(doc, reference_key)
        if name:
            label = f"{name}, {number}"
    reference_link = cite_as_link(label, google_patents_url(reference_key))
    application_link = cite_as_link(
        f"Application {app_number}" if app_number else None,
        patent_center_url(app_number),
    )
    return reference_link, application_link


def citation_links_for_docs(
    docs: Any, reference_keys: Sequence[Optional[str]], *, compact: bool = False
) -> List[CitationLinks]:
    """Both links for each record, positionally. Computed from the UNFILTERED
    upstream docs, for the same reason `referenceKey` is: a tier or a custom
    `fields` list can drop the name and application fields the link is built
    from, and the caller who asked for the smallest rows still needs a citable
    link on them."""
    if not isinstance(docs, list):
        return []
    return [
        citation_links_for_doc(doc, key, compact=compact)
        for doc, key in zip(docs, list(reference_keys) + [None] * len(docs))
    ]


def attach_citation_links(
    docs: Any, links: Sequence[CitationLinks], *, application: bool = True
) -> None:
    """Attach `cite_as` (and, when `application`, `application_cite_as`) to
    each record, in place, positionally.

    `cite_as` is ALWAYS set, `None` included, and both keys are attached AFTER
    the tier's field filtering so they survive every tier and every custom
    field list. A null says this row has no verified public record link.
    `application` is False on the narrow shapes unless the caller's `fields`
    list named `application_cite_as` (see wants_application_link).
    """
    if not isinstance(docs, list):
        return
    for doc, (reference_link, application_link) in zip(docs, links):
        if isinstance(doc, dict):
            doc[CITE_AS_FIELD] = reference_link
            if application:
                doc[APPLICATION_CITE_AS_FIELD] = application_link


def attach_citation_links_to_doc(doc: Any, reference_key: Optional[str]) -> None:
    """Attach both links to a single record (the details lane), in place."""
    attach_citation_links([doc], [citation_links_for_doc(doc, reference_key)])
