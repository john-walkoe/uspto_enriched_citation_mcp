"""Helpers shared by more than one tool module (avoids import cycles between
tools/search.py and tools/oa.py)."""

from typing import Any, Dict, List, Optional


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
