"""Query validation utilities for Lucene syntax with enhanced security."""

import re
from typing import Optional, Tuple, Set
from .security_logger import get_security_logger, query_fingerprint
from ..config.constants import (
    MAX_QUERY_LENGTH,
    MAX_WILDCARDS_PER_QUERY,
    MAX_QUERY_NESTING_DEPTH,
    MAX_RANGE_QUERIES,
)

# Field whitelist from field_configs.yaml and USPTO API documentation
VALID_FIELDS: Set[str] = {
    # Core citation fields
    "patentApplicationNumber",
    "publicationNumber",
    "groupArtUnitNumber",
    "citedDocumentIdentifier",
    "citationCategoryCode",
    "techCenter",
    "officeActionDate",
    "examinerCitedReferenceIndicator",
    # Analysis fields
    "passageLocationText",
    "officeActionCategory",
    "relatedClaimNumberText",
    "nplIndicator",
    "workGroupNumber",
    "kindCode",
    "countryCode",
    "qualitySummaryText",
    "inventorNameText",
    "applicantCitedExaminerReferenceIndicator",
    "createDateTime",
    "createUserIdentifier",
    "obsoleteDocumentIdentifier",
    "id",
}

# OA Citations v2 field whitelist (Form 892/1449 raw-citation API). The OA
# search tools pass this as valid_fields — the default VALID_FIELDS above is
# the Enriched Citations v3 schema, and 7 OA-only fields (legalSectionCode,
# actionTypeCategory, referenceIdentifier, ...) would be wrongly rejected.
# (Regression found live 2026-07-09: the OA tools' validator call was dead
# code until audit fix H3 made it real, exposing the missing field set.)
OA_VALID_FIELDS: Set[str] = {
    "patentApplicationNumber",
    "groupArtUnitNumber",
    "techCenter",
    "referenceIdentifier",
    "parsedReferenceIdentifier",
    "actionTypeCategory",
    "legalSectionCode",
    "examinerCitedReferenceIndicator",
    "applicantCitedExaminerReferenceIndicator",
    "officeActionCitationReferenceIndicator",
    "workGroup",
    "paragraphNumber",
    "createDateTime",
    "createUserIdentifier",
    "obsoleteDocumentIdentifier",
    "id",
}

# Valid Lucene operators
VALID_OPERATORS: Set[str] = {"AND", "OR", "NOT", "TO"}

# Type returned by each `_check_*` helper: None on success, or (False, message)
# on failure. `validate_lucene_syntax` walks the helpers in order and returns
# on the first failure.
_CheckResult = Optional[Tuple[bool, str]]


def _check_not_empty(query: str) -> _CheckResult:
    """Reject empty/whitespace-only queries. Logs to the security audit trail."""
    if not query or not query.strip():
        security_logger = get_security_logger()
        security_logger.query_validation_failure(
            query="", reason="Empty query", severity="low"
        )
        return False, "Query cannot be empty"
    return None


def _check_length(query: str) -> _CheckResult:
    """Prevent DoS via oversized queries."""
    if len(query) > MAX_QUERY_LENGTH:
        return False, f"Query too long (max {MAX_QUERY_LENGTH} characters)"
    return None


def _check_injection_patterns(query: str) -> _CheckResult:
    """Reject script/template/command injection patterns. Logs attempts."""
    dangerous_patterns = [
        r"<script",
        r"javascript:",
        r"\\x[0-9a-f]{2}",
        r"\\u[0-9a-f]{4}",
        r"\$\{",  # Template injection
        r"`",  # Command injection
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            # Log injection attempt
            security_logger = get_security_logger()
            security_logger.injection_attempt(
                injection_type="query_injection",
                input_field="lucene_query",
                pattern_detected=pattern,
                query_len=len(query),
                query_sha=query_fingerprint(query),
            )
            return False, "Query contains potentially dangerous patterns"
    return None


def _check_balanced_parens_and_brackets(query: str) -> _CheckResult:
    """Validate balanced parentheses/brackets and cap nesting depth (DoS)."""
    paren_count = 0
    bracket_count = 0
    for char in query:
        if char == "(":
            paren_count += 1
        elif char == ")":
            paren_count -= 1
        elif char == "[":
            bracket_count += 1
        elif char == "]":
            bracket_count -= 1

        # Prevent excessive nesting (DoS protection)
        if (
            paren_count > MAX_QUERY_NESTING_DEPTH
            or bracket_count > MAX_QUERY_NESTING_DEPTH
        ):
            return (
                False,
                f"Query nesting too deep (max {MAX_QUERY_NESTING_DEPTH} levels)",
            )

        if paren_count < 0 or bracket_count < 0:
            return False, "Unbalanced parentheses or brackets"

    if paren_count != 0:
        return False, "Unbalanced parentheses"
    if bracket_count != 0:
        return False, "Unbalanced brackets"
    return None


def _check_balanced_quotes(query: str) -> _CheckResult:
    """Validate balanced double quotes."""
    quote_count = query.count('"')
    if quote_count % 2 != 0:
        return False, "Unbalanced quotes"
    return None


def _check_malformed_boolean_or_range(query: str) -> _CheckResult:
    """Reject malformed boolean expressions and incomplete range expressions."""
    # Reject "field:" immediately followed by whitespace, end-of-query, or a
    # boolean operator — i.e. a field query with no value.
    if re.search(r"(\w+):\s*(?:\s|$|AND|OR|NOT)", query):
        return False, "Field queries must have non-empty values"

    # Reject a boolean operator (AND/OR/NOT) as the first token — it has no
    # left-hand operand to combine.
    if re.search(r"^\s*(AND|OR|NOT)\s+", query):
        return False, "Query cannot start with a boolean operator"

    # Reject AND/OR as the last token — a binary operator with no right-hand
    # operand.
    if re.search(r"(AND|OR)\s*$", query):
        return False, "Incomplete boolean expression"

    # Reject a range "[lower TO" that ends before its upper bound and closing
    # bracket.
    if re.search(r"\[.*TO\s*$", query):
        return False, "Incomplete range expression"

    return None


def _check_field_whitelist(query: str, valid_fields: Set[str]) -> _CheckResult:
    """Validate field names and values (security-critical). Logs invalid access."""
    # Colons inside "[...]" range bodies (ISO-8601 timestamps like
    # createDateTime:[2025-01-01T00:00:00Z TO *]) and inside quoted phrases
    # are VALUES, not field references — strip those spans first or the
    # regex below misreads "00:00" as a field named "01T00" (found live
    # 2026-07-09, TEST_SUITE.md OA-9). Same idiom as _check_wildcards.
    scannable = re.sub(r"\[[^\]]+\]", "", query)
    scannable = re.sub(r'"[^"]*"', "", scannable)
    # Every remaining "word:" prefix is a field reference — collect them all
    # for the whitelist check below.
    field_pattern = r"(\w+):"
    fields_used = re.findall(field_pattern, scannable)

    for field in fields_used:
        # Check against whitelist
        if field not in valid_fields and field.upper() not in VALID_OPERATORS:
            # Log invalid field access attempt
            security_logger = get_security_logger()
            security_logger.invalid_field_access(
                field_name=field,
                attempted_operation="lucene_query",
                query_len=len(query),
                query_sha=query_fingerprint(query),
            )
            return (
                False,
                f"Invalid field name: {field}. Use Citations_get_available_fields tool for valid fields.",
            )
    return None


def _check_range_count(query: str) -> _CheckResult:
    """Cap the number of "[lower TO upper]" range expressions (DoS protection)."""
    range_pattern = r"\[([^\]]+) TO ([^\]]+)\]"
    ranges = re.findall(range_pattern, query)
    if len(ranges) > MAX_RANGE_QUERIES:
        return False, f"Too many range queries (max {MAX_RANGE_QUERIES})"
    return None


def _check_character_set(query: str) -> _CheckResult:
    """Restrict allowed characters (more restrictive than before).

    Allow: alphanumeric, field separator (:), wildcards (*?), quotes ("),
    parentheses (()), brackets ([]), hyphen (-), space, boolean operators
    (&|!), range (TO), and basic punctuation (.,_).
    """
    if not re.match(r'^[a-zA-Z0-9:*?"()\[\]\-\s&|!.,_]+$', query):
        return False, "Query contains invalid characters"
    return None


def _check_wildcards(query: str) -> _CheckResult:
    """Prevent excessive and leading wildcards (DoS / performance protection)."""
    # Additional security: prevent excessive wildcards (DoS)
    wildcard_count = query.count("*") + query.count("?")
    if wildcard_count > MAX_WILDCARDS_PER_QUERY:
        # Log excessive wildcards (DoS indicator)
        security_logger = get_security_logger()
        security_logger.excessive_wildcards(
            query=query,
            wildcard_count=wildcard_count,
            max_allowed=MAX_WILDCARDS_PER_QUERY,
        )
        return False, f"Too many wildcards (max {MAX_WILDCARDS_PER_QUERY})"

    # Prevent leading wildcards (performance issue) - but allow in range queries
    # First strip all "[...]" range bodies (their "*" bounds are legitimate),
    # then reject "*" at the start of the query or of any whitespace-separated term.
    query_without_ranges = re.sub(r"\[[^\]]+\]", "", query)
    if re.search(r"^\*|\s\*", query_without_ranges):
        return False, "Leading wildcards are not allowed (performance issue)"

    return None


def validate_lucene_syntax(
    query: str, valid_fields: Optional[Set[str]] = None
) -> Tuple[bool, str]:
    """
    Enhanced Lucene query validation with security checks.

    Validates:
    - Field names against whitelist
    - Balanced parentheses and quotes
    - Nesting depth limits
    - Character restrictions
    - Length limits
    - Injection patterns

    All validation failures are logged to security audit trail.

    Args:
        query: Lucene query string to validate
        valid_fields: Field whitelist for this API — defaults to the Enriched
            Citations v3 set (VALID_FIELDS); OA tools pass OA_VALID_FIELDS

    Returns:
        Tuple of (is_valid, message)
    """
    fields = valid_fields if valid_fields is not None else VALID_FIELDS

    empty_result = _check_not_empty(query)
    if empty_result is not None:
        return empty_result

    query = query.strip()

    for check in (
        _check_length,
        _check_injection_patterns,
        _check_balanced_parens_and_brackets,
        _check_balanced_quotes,
        _check_malformed_boolean_or_range,
        lambda q: _check_field_whitelist(q, fields),
        _check_range_count,
        _check_character_set,
        _check_wildcards,
    ):
        result = check(query)
        if result is not None:
            return result

    return True, "Query validation passed"
