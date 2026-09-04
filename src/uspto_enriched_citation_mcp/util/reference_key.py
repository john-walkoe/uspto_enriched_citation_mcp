"""Cross-lane citation reference key.

The two citation lanes write the same reference differently. Measured on
application 12849948 (2026-09-04):

    OA (v2)        parsedReferenceIdentifier   "20060075466"
    Enriched (v3)  citedDocumentIdentifier     "US 2006/0075466 A1"
    Enriched (v3)  publicationNumber           "20060075466"

A client that unions the two lanes on `parsedReferenceIdentifier` against
`citedDocumentIdentifier` therefore finds zero overlap on every application,
when the true answer on that application is four references in both lanes. The
OA minimal tier makes it worse: it carries no parsed identifier at all, only
the raw Form 892 string in `referenceIdentifier` with the inventor name
attached.

`normalize_reference_key` collapses all four of those forms onto one value, and
both lanes attach it to every record as `referenceKey`, at every tier, so the
join key is served rather than reconstructed by each caller.

Normalisation: uppercase, drop a leading `US` country code, drop spaces,
slashes, hyphens, commas and periods, drop a trailing kind code (`A1`, `B2`,
`E`, `S`, ...), and keep a leading series marker (`RE`, `D`, `PP`, ...). A
value that does not reduce to a plausible document number - non-patent
literature, a free-text citation, a blank - normalises to `None`, which is the
honest answer: that row cannot be joined across lanes.
"""

import re
from typing import Any, Dict, List, Optional, Sequence

#: Record key carrying the normalised cross-lane join value. Present on every
#: citation record on both lanes at every tier; `None` when the row's
#: identifier does not reduce to a document number.
REFERENCE_KEY_FIELD = "referenceKey"

#: Enriched (v3) fields that can carry the cited reference, best source first.
#: `publicationNumber` is already digits, so it is preferred; the tester round
#: found rows where it is empty and `citedDocumentIdentifier` is null, empty or
#: absent, which is why both are tried and `None` is a real outcome.
ENRICHED_REFERENCE_SOURCE_FIELDS: Sequence[str] = (
    "publicationNumber",
    "citedDocumentIdentifier",
)

#: OA (v2) fields that can carry the cited reference, best source first. The
#: minimal tier carries only `referenceIdentifier` (the raw 892 string), which
#: is why the raw form has to normalise as well as the parsed one.
OA_REFERENCE_SOURCE_FIELDS: Sequence[str] = (
    "parsedReferenceIdentifier",
    "referenceIdentifier",
)

# Separators that appear inside a written patent number.
_SEPARATORS = re.compile(r"[\s/\-,._]")
# A leading US country code, only when something follows it.
_LEADING_US = re.compile(r"^US(?=[0-9A-Z])")
# A kind code is a trailing letter (plus optional digit) that follows a digit,
# so it never eats a leading series marker such as RE.
_TRAILING_KIND_CODE = re.compile(r"(?<=\d)[A-Z]\d?$")
# What a normalised key is allowed to look like: an optional short series or
# country marker, then 5 to 13 digits. The 5-digit floor is what keeps a year
# or a page range inside a non-patent-literature citation from being mistaken
# for a document number.
_KEY_SHAPE = re.compile(r"^[A-Z]{0,3}\d{5,13}$")

# How many leading whitespace tokens to try joining. A raw 892 string puts the
# reference first and the inventor name after it, so the reference is always
# inside the first few tokens; anything longer is prose.
_MAX_PREFIX_TOKENS = 3


def _as_text(value: Any) -> Optional[str]:
    """Coerce one field value to text, or None if it cannot carry a reference."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _as_text(item)
            if text:
                return text
    return None


def _normalize_candidate(candidate: str) -> Optional[str]:
    """Normalise one candidate span; None when it is not a document number."""
    cleaned = _SEPARATORS.sub("", candidate.upper().strip("()[]{}\"';:"))
    if not cleaned:
        return None
    cleaned = _LEADING_US.sub("", cleaned)
    cleaned = _TRAILING_KIND_CODE.sub("", cleaned)
    return cleaned if _KEY_SHAPE.match(cleaned) else None


def normalize_reference_key(value: Any) -> Optional[str]:
    """Normalise one reference identifier to the cross-lane `referenceKey`.

    Returns the normalised key, or None when the value does not reduce to a
    plausible document number (non-patent literature, free text, blank, or a
    missing field).
    """
    text = _as_text(value)
    if not text or not text.strip():
        return None

    tokens = text.split()
    # The whole value first (it is the common case: one written number), then
    # progressively shorter leading spans, so "US 9,280,610 B2 to Smith" and
    # "20060075466 A1 KAWAI" both resolve while prose does not.
    candidates = [text] + [
        " ".join(tokens[:n]) for n in range(_MAX_PREFIX_TOKENS, 0, -1)
    ]
    for candidate in candidates:
        key = _normalize_candidate(candidate)
        if key is not None:
            return key
    return None


def reference_key_for_doc(doc: Any, source_fields: Sequence[str]) -> Optional[str]:
    """The `referenceKey` for one citation record, from the first field that
    yields one. `source_fields` is best source first."""
    if not isinstance(doc, dict):
        return None
    for field in source_fields:
        key = normalize_reference_key(doc.get(field))
        if key is not None:
            return key
    return None


def reference_keys_for_docs(
    docs: Any, source_fields: Sequence[str]
) -> List[Optional[str]]:
    """The `referenceKey` for each record, positionally. Computed from the
    UNFILTERED upstream docs so a tier that drops the best source field still
    gets the best key."""
    if not isinstance(docs, list):
        return []
    return [reference_key_for_doc(doc, source_fields) for doc in docs]


def attach_reference_keys(docs: Any, keys: Sequence[Optional[str]]) -> None:
    """Attach `referenceKey` to each record, in place, positionally.

    The key is ALWAYS set, `None` included: a client joining two lanes needs to
    see that a row has no joinable identifier, and an absent key would read as
    an older server rather than as an unjoinable row.
    """
    if not isinstance(docs, list):
        return
    for doc, key in zip(docs, keys):
        if isinstance(doc, dict):
            doc[REFERENCE_KEY_FIELD] = key


def count_rows_without_reference(keys: Sequence[Optional[str]]) -> int:
    """How many records carry no joinable reference identifier at all.

    Absent, null and empty are ONE state here: each of them normalises to None,
    and each of them means the same thing to a caller unioning the lanes."""
    return sum(1 for key in keys if key is None)


def annotate_docs(
    payload: Dict[str, Any], source_fields: Sequence[str]
) -> List[Optional[str]]:
    """Compute and attach `referenceKey` for a search payload's docs, in place.

    Returns the key list so a caller can also report
    `rows_without_reference_identifier` without walking the docs twice.
    """
    docs = payload.get("response", {}).get("docs") if isinstance(payload, dict) else None
    keys = reference_keys_for_docs(docs, source_fields)
    attach_reference_keys(docs, keys)
    return keys
