"""Helpers shared by more than one tool module (avoids import cycles between
tools/search.py and tools/oa.py)."""

import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .. import runtime
from ..config.constants import MAX_PAGINATION_START
from ..shared.error_utils import format_error_response
# Re-exported for the tool modules that import it from here; the template
# itself lives in shared/pfw_link.py so tools and services share one
# definition rather than two copies of the same sentence (D-9).
from ..shared.pfw_link import PFW_LINK_HINT  # noqa: F401
from ..util.patent_crosswalk import (
    PatentCrosswalkError,
    PatentNumberResolution,
    resolve_patent_number_param,
)


def _build_query_info(
    query: str,
    tier: str,
    *,
    parameters: Optional[Dict[str, Any]] = None,
    custom_fields: Optional[List[str]] = None,
    field_count: Optional[int] = None,
    api: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the query_info response block shared by the search tools.

    Enriched-citation tools pass parameters/custom_fields/field_count (plus
    per-tool extras); OA Citations tools pass api. Key order matches the
    original per-tool dict literals.
    """
    info: Dict[str, Any] = {"constructed_query": query}
    if parameters is not None:
        info["parameters"] = parameters
    info["tier"] = tier
    if field_count is not None:
        info["custom_fields"] = custom_fields
        info["field_count"] = field_count
    if api is not None:
        info["api"] = api
    if extra:
        info.update(extra)
    return info


#: Whole-tool deadline, in seconds. Each hop was bounded and the call was
#: not: three retry attempts at the 30s HTTP timeout plus backoff is about
#: 93 seconds before the caller sees anything, and get_citation_statistics
#: fans out six of those. Any reverse proxy in front of this cuts the
#: connection first, so the caller gets a proxy error instead of the
#: server's own degraded response (R-5). 45s leaves room for one retry plus
#: backoff and lands inside every plausible proxy budget.
DEFAULT_TOOL_DEADLINE_SECONDS = 45.0


def tool_deadline_seconds() -> float:
    """Read the deadline per call so a deployment can tune it without a
    restart-time constant, and so tests can set it."""
    raw = os.getenv("CITATIONS_TOOL_DEADLINE", "")
    if not raw:
        return DEFAULT_TOOL_DEADLINE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TOOL_DEADLINE_SECONDS
    return value if value > 0 else DEFAULT_TOOL_DEADLINE_SECONDS


async def run_with_deadline(
    coro_factory: Callable[[], Awaitable[Dict[str, Any]]], label: str
) -> Dict[str, Any]:
    """Run a tool body under the whole-call deadline.

    Returns the body's result, or a 504 envelope naming the deadline. 504 is
    the honest code: the server gave up waiting on an upstream, which is what
    an agent should back off from rather than retry immediately.
    """
    deadline = tool_deadline_seconds()
    try:
        async with asyncio.timeout(deadline):
            return await coro_factory()
    except TimeoutError:
        return format_error_response(
            f"{label} exceeded the {deadline:.0f}s server deadline. Narrow the "
            f"query or retry; the upstream USPTO API did not answer in time.",
            504,
        )


def validate_pagination(
    rows: int, start: int, max_rows: int, max_rows_message: str
) -> Optional[Dict[str, Any]]:
    """Bound both pagination arguments in both directions.

    `rows` was capped and `start` was not, and neither had a floor, so
    `rows=-1` and `start=-1` reached Solr and `start=50000000` forced a deep
    page upstream. Returns an error response, or None when the pair is
    acceptable.
    """
    if rows < 1:
        return format_error_response("rows must be at least 1", 400)
    if rows > max_rows:
        return format_error_response(max_rows_message, 400)
    if start < 0:
        return format_error_response("start must be 0 or greater", 400)
    if start > MAX_PAGINATION_START:
        return format_error_response(
            f"start must be {MAX_PAGINATION_START} or less; narrow the query "
            f"rather than paging deeper",
            400,
        )
    return None


async def _resolve_patent_number(
    patent_number: Optional[str],
    application_number: Optional[str] = None,
    *,
    allow_publication: bool = True,
) -> Tuple[Optional[PatentNumberResolution], Optional[Dict[str, Any]]]:
    """Interpret a tool's `patent_number` argument for the calling lane.

    Returns (resolution, error_response) with exactly one of them set, and
    (None, None) when the caller passed no patent number at all. Every failure
    is a caller error carrying the accepted identifier forms, so a wrong
    identifier reads as a 400 that says what to pass instead of a successful
    search that found nothing.
    """
    if not patent_number or not patent_number.strip():
        return None, None

    try:
        resolution = await resolve_patent_number_param(
            patent_number,
            application_number,
            resolver=runtime.crosswalk_client.find_application_number,
            allow_publication=allow_publication,
        )
    except PatentCrosswalkError as e:
        return None, format_error_response(str(e), 400)

    return resolution, None


def _apply_resolution(
    resolution: Optional[PatentNumberResolution],
    patent_number: Optional[str],
    application_number: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Rewrite (patent_number, application_number) for the resolved reading.

    A crosswalked granted patent number moves onto the application-number
    clause and leaves `patent_number` empty (the index has no field for it); a
    publication number stays on `patent_number` in normalized form. Extracted
    with `_attach_patent_number_resolution` so the two enriched search tools
    stay under the C901 ceiling, the same reason `_attach_query_advisories`
    exists.
    """
    if resolution is None:
        return patent_number, application_number
    if resolution.application_number:
        return None, resolution.application_number
    return resolution.publication_number, application_number


def _attach_patent_number_resolution(
    payload: Dict[str, Any], resolution: Optional[PatentNumberResolution]
) -> None:
    """Attach the patent_number self-report, in place. ABSENT when the caller
    passed no patent number."""
    if resolution is not None:
        payload["patent_number_resolution"] = resolution.note


def _attach_query_advisories(
    payload: Dict[str, Any],
    warnings: List[str],
    coverage_notes: List[str],
) -> None:
    """Attach build_query's advisory blocks to a search response, in place.

    Both keys are ABSENT when empty. `warnings` are hard problems with the
    query; `coverage_notes` are soft, advisory statements about what the
    index is likely to hold — they must never read as a refusal.
    """
    if warnings:
        payload["warnings"] = warnings
    if coverage_notes:
        payload["coverage_notes"] = coverage_notes
