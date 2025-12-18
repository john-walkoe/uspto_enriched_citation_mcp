"""Query validation utilities for Lucene syntax with enhanced security."""

import re
from typing import Tuple, Set
from .security_logger import get_security_logger
from ..config.constants import (
    MAX_QUERY_LENGTH,
    MAX_WILDCARDS_PER_QUERY,
    MAX_QUERY_NESTING_DEPTH,
    MAX_RANGE_QUERIES,
    LOG_QUERY_PREVIEW_LENGTH,
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

# Valid Lucene operators
VALID_OPERATORS: Set[str] = {"AND", "OR", "NOT", "TO"}


def validate_lucene_syntax(query: str) -> Tuple[bool, str]:
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

    Returns:
        Tuple of (is_valid, message)
    """
    if not query or not query.strip():
        security_logger = get_security_logger()
        security_logger.query_validation_failure(
            query="", reason="Empty query", severity="low"
        )
        return False, "Query cannot be empty"

    query = query.strip()

    # Check length limitations (prevent DoS)
    if len(query) > MAX_QUERY_LENGTH:
        return False, f"Query too long (max {MAX_QUERY_LENGTH} characters)"

    # Check for injection patterns
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
                query_preview=query[:LOG_QUERY_PREVIEW_LENGTH],
            )
            return False, "Query contains potentially dangerous patterns"

    # Validate balanced parentheses
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

    # Validate balanced quotes
    quote_count = query.count('"')
    if quote_count % 2 != 0:
        return False, "Unbalanced quotes"

    # Validate field names and values (security-critical)
    # Extract field:value patterns
    field_pattern = r"(\w+):"
    fields_used = re.findall(field_pattern, query)

    # Check for empty field values (field: with no value)
    if re.search(r"(\w+):\s*(?:\s|$|AND|OR|NOT)", query):
        return False, "Field queries must have non-empty values"

    # Check for leading boolean operators
    if re.search(r"^\s*(AND|OR|NOT)\s+", query):
        return False, "Query cannot start with a boolean operator"

    # Check for incomplete boolean expressions
    if re.search(r"(AND|OR)\s*$", query):
        return False, "Incomplete boolean expression"

    # Check for incomplete range expressions
    if re.search(r"\[.*TO\s*$", query):
        return False, "Incomplete range expression"

    for field in fields_used:
        # Check against whitelist
        if field not in VALID_FIELDS and field.upper() not in VALID_OPERATORS:
            # Log invalid field access attempt
            security_logger = get_security_logger()
            security_logger.invalid_field_access(
                field_name=field,
                attempted_operation="lucene_query",
                query_preview=query[:LOG_QUERY_PREVIEW_LENGTH],
            )
            return (
                False,
                f"Invalid field name: {field}. Use get_available_fields tool for valid fields.",
            )

    # Validate range queries
    range_pattern = r"\[([^\]]+) TO ([^\]]+)\]"
    ranges = re.findall(range_pattern, query)
    if len(ranges) > MAX_RANGE_QUERIES:
        return False, f"Too many range queries (max {MAX_RANGE_QUERIES})"

    # Restrict allowed characters (more restrictive than before)
    # Allow: alphanumeric, field separator (:), wildcards (*?), quotes ("),
    # parentheses (()), brackets ([]), hyphen (-), space, boolean operators (&|!),
    # range (TO), and basic punctuation (.,_)
    if not re.match(r'^[a-zA-Z0-9:*?"()\[\]\-\s&|!.,_]+$', query):
        return False, "Query contains invalid characters"

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
    # First remove range query content to avoid false positives
    query_without_ranges = re.sub(r"\[[^\]]+\]", "", query)
    if re.search(r"^\*|\s\*", query_without_ranges):
        return False, "Leading wildcards are not allowed (performance issue)"

    return True, "Query validation passed"
