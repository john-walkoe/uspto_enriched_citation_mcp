"""Granted-patent-number crosswalk for the citation search tools.

Neither citation index can be searched by granted patent number. The enriched
lane's `publicationNumber` holds 11-digit PRE-GRANT publication numbers, so a
granted patent number sent there matches nothing and returns a clean zero that
reads as "never cited"; the OA lane has no patent-number field at all
(`publicationNumber` returns HTTP 400 there).

This module normalizes whatever the caller passed as `patent_number` and, when
it is a granted patent number, resolves it to the application serial both
indexes DO carry (`patentApplicationNumber`) via one call to the USPTO ODP
applications search API. The resolver itself is injected — the HTTP work lives
in `api/applications_client.py`, which routes through the same metered client
stack as every other outbound call.

Every outcome is reported to the caller: `patent_number_resolution` says how
the input was read and, when crosswalked, which application it became.
"""

import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

GRANTED_PATENT = "granted_patent"
PUBLICATION = "publication"

#: Provenance stamped on a crosswalked resolution note.
CROSSWALK_SOURCE = "USPTO ODP applications search"

#: Named in every rejection so the caller learns the whole accepted vocabulary
#: from one error rather than one form at a time.
ACCEPTED_FORMS = (
    "Accepted forms: a granted patent number (7-8 digits, e.g. 7971071 or "
    "7,971,071), an 11-digit pre-grant publication number (e.g. 20060075466), "
    "or an application serial passed as `application_number` (e.g. 11752072)."
)

_SEPARATORS = re.compile(r"[\s,]+")
_US_PREFIX = re.compile(r"^US-?", re.IGNORECASE)
_DIGITS_ONLY = re.compile(r"[^0-9]")


class PatentCrosswalkError(ValueError):
    """Base class for caller-facing patent_number failures (all map to 400)."""


class PatentNumberFormatError(PatentCrosswalkError):
    """The value is not a recognized identifier shape for this lane."""


class PatentNumberNotFoundError(PatentCrosswalkError):
    """A well-formed granted patent number that USPTO could not resolve."""


class PatentNumberConflictError(PatentCrosswalkError):
    """patent_number and application_number name different applications."""


@dataclass(frozen=True)
class NormalizedPatentNumber:
    """A cleaned patent_number plus the namespace it was read as."""

    raw: str
    number: str
    kind: str


@dataclass(frozen=True)
class PatentNumberResolution:
    """Outcome of interpreting one `patent_number` argument.

    Exactly one of `application_number` (granted patent, crosswalked) and
    `publication_number` (11-digit pre-grant publication, queried directly) is
    set. `note` is the self-report attached to the tool response as
    `patent_number_resolution`.
    """

    note: Dict[str, Any]
    application_number: Optional[str] = None
    publication_number: Optional[str] = None


def normalize_patent_number(value: str) -> NormalizedPatentNumber:
    """Read a caller-supplied patent number into a digit string plus a kind.

    Commas and whitespace are removed and a leading `US` (with or without a
    hyphen) is dropped, so "7,971,071", "US 7971071" and "7971071" are the same
    input. What remains must be all digits and either 7-8 digits (a granted
    patent number) or 11 digits (a pre-grant publication number). Anything else
    is refused by name instead of being sent to an index that would answer zero.
    """
    raw = value if isinstance(value, str) else str(value)
    cleaned = _SEPARATORS.sub("", raw)
    cleaned = _US_PREFIX.sub("", cleaned, count=1)

    if not cleaned or not cleaned.isdigit():
        raise PatentNumberFormatError(
            f"Unrecognized patent_number '{raw.strip()}'. {ACCEPTED_FORMS}"
        )

    if len(cleaned) in (7, 8):
        kind = GRANTED_PATENT
    elif len(cleaned) == 11:
        kind = PUBLICATION
    else:
        raise PatentNumberFormatError(
            f"patent_number '{raw.strip()}' has {len(cleaned)} digits, which is "
            f"neither a granted patent number nor a publication number. "
            f"{ACCEPTED_FORMS}"
        )

    return NormalizedPatentNumber(raw=raw.strip(), number=cleaned, kind=kind)


def _digits(value: str) -> str:
    """Digits of an identifier, so '11/752,072' compares equal to '11752072'."""
    return _DIGITS_ONLY.sub("", value or "")


async def resolve_patent_number_param(
    patent_number: str,
    application_number: Optional[str] = None,
    *,
    resolver: Callable[[str], Awaitable[Optional[str]]],
    allow_publication: bool = True,
) -> PatentNumberResolution:
    """Interpret `patent_number` for one lane, crosswalking when needed.

    Args:
        patent_number: the caller's raw value.
        application_number: the caller's `application_number`, if any — a
            crosswalk that disagrees with it is refused rather than ANDed into
            a query that can only return zero.
        resolver: async callable taking a granted patent number and returning
            an application serial or None.
        allow_publication: False on the OA lane, which has no publication
            field, so an 11-digit publication number is refused there instead
            of being silently treated as something else.

    Raises:
        PatentCrosswalkError subclasses, all caller errors (400).
    """
    normalized = normalize_patent_number(patent_number)

    if normalized.kind == PUBLICATION:
        if not allow_publication:
            raise PatentNumberFormatError(
                f"'{normalized.raw}' is an 11-digit pre-grant publication number, "
                "which the Office Action Citations lane cannot search (it has no "
                "publication-number field). Pass a granted patent number, or use "
                "Citations_search_citations_minimal for publication numbers."
            )
        return PatentNumberResolution(
            note={
                "input": normalized.raw,
                "interpreted_as": PUBLICATION,
                "queried_field": "publicationNumber",
            },
            publication_number=normalized.number,
        )

    resolved = await resolver(normalized.number)
    if not resolved:
        raise PatentNumberNotFoundError(
            f"No USPTO application found for patent number '{normalized.raw}'. "
            f"{ACCEPTED_FORMS}"
        )

    if application_number and _digits(application_number) != _digits(resolved):
        raise PatentNumberConflictError(
            f"patent_number '{normalized.raw}' resolves to application "
            f"{resolved}, which conflicts with the application_number "
            f"'{application_number.strip()}' you also passed. Pass one of them, "
            "or pass values that name the same application."
        )

    return PatentNumberResolution(
        note={
            "input": normalized.raw,
            "interpreted_as": GRANTED_PATENT,
            "resolved_application_number": resolved,
            "queried_field": "patentApplicationNumber",
            "source": CROSSWALK_SOURCE,
        },
        application_number=resolved,
    )
