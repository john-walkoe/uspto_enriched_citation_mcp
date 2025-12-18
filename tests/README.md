# Test Suite

This directory contains the test scripts for the USPTO Enriched Citation MCP Server.

## Available MCP Tools (7 Total)

The server provides these tools for citation research:

### Search Tools (Progressive Disclosure)
- **`search_citations_minimal`** - Minimal fields (8 fields, 90-95% context reduction)
- **`search_citations_balanced`** - Balanced fields (18 fields, 80-85% context reduction)
- **`search_citations`** - Full search with custom field selection (ultra-minimal mode: 99% reduction)

### Analysis Tools
- **`get_citation_details`** - Get complete citation record with all available fields
- **`get_citation_statistics`** - Aggregate statistics for strategic intelligence
- **`get_available_fields`** - List all 22 searchable fields with descriptions
- **`validate_query`** - Lucene syntax validation and optimization suggestions

## Essential Tests

### Core Functionality Tests
- **`test_basic.py`** - Core functionality with mocked API responses
  - Client initialization
  - Field retrieval
  - Basic search operations
  - Query validation (Lucene syntax)
  - Citation details
  - Boolean, range, and wildcard query validation
  - Special character handling
  - Error response formatting

- **`test_field_configuration.py`** - YAML field configuration system
  - Field manager loading from field_configs.yaml
  - Predefined field sets (minimal, balanced)
  - Custom field validation
  - Response filtering
  - Field validation logic

- **`test_convenience_parameters.py`** - Convenience parameter implementation
  - Tech center, art unit, application number parameters
  - Date range convenience parameters
  - Citation category and examiner citation filters
  - Parameter validation and edge cases
  - Query building with multiple parameters

### Integration Tests
- **`test_integration.py`** - End-to-end workflows with real API calls
  - Progressive disclosure (minimal → balanced → detailed)
  - Field management and custom fields
  - Query syntax validation
  - Convenience parameters
  - Citation analysis (categories, examiner vs applicant)
  - Date range handling (2017-10-01 constraint)
  - Error handling and edge cases
  - Performance and pagination
  - Complete workflow testing

### Security Tests
- **`test_security.py`** - Security features and attack prevention
  - Security event logging (auth, rate limits, injection attempts)
  - Prompt injection detection patterns
  - Input validation and sanitization
  - Unicode steganography detection
  - Query validation failure logging
  - Invalid field access detection

### Resilience Tests
- **`test_resilience.py`** - API resilience and failure handling
  - Token bucket rate limiting algorithm
  - Circuit breaker pattern (open/closed/half-open states)
  - Retry logic with exponential backoff
  - Response caching (LRU cache)
  - Rate limit enforcement
  - Failure recovery mechanisms

### Statistics Tests
- **`test_statistics.py`** - Citation statistics and aggregations
  - Basic statistics retrieval
  - Category distribution analysis
  - Examiner vs applicant citation stats
  - Date range statistics
  - Large dataset performance
  - Empty result handling

### Cross-MCP Integration Tests
- **`test_unified_key_management.py`** - Unified secure storage for API keys
  - Windows DPAPI encryption/decryption
  - Unified key management across USPTO MCPs (PFW, FPD, PTAB, Citations)
  - Environment variable fallback
  - Cross-MCP compatibility

## API Key Setup

### Option 1: Windows DPAPI Secure Storage (Recommended for Windows)

API keys stored in Windows DPAPI secure storage are encrypted and persistent across sessions:

```bash
# Check what keys are stored (validates presence only, no actual values displayed)
uv run python -c "from uspto_enriched_citation_mcp.shared.shared_secure_storage import get_api_key; print('Key present' if get_api_key('USPTO_API_KEY') else 'No key')"
```

Keys are automatically loaded from secure storage with environment variable fallback. See `SECURITY_GUIDELINES.md` for setup instructions.

### Option 2: Environment Variables

```bash
# Windows Command Prompt
set USPTO_API_KEY=your_api_key_here

# Windows PowerShell
$env:USPTO_API_KEY="your_api_key_here"

# Linux/macOS
export USPTO_API_KEY=your_api_key_here
```

**Environment Variable Options**:
- `USPTO_API_KEY` - Required if not using DPAPI
- `ECITATION_RATE_LIMIT` - Requests per minute (default: 100)
- `API_TIMEOUT` - Request timeout in seconds (default: 30)
- `ENABLE_CACHE` - Enable response caching (default: true)

### Option 3: Testing Without Real API Key

If you don't have a USPTO API key yet, unit tests (`test_basic.py`, `test_field_configuration.py`, `test_convenience_parameters.py`, `test_security.py`, `test_resilience.py`) will use a mock key for testing code structure. However, integration tests (`test_integration.py`, `test_statistics.py`) require a real key and will be skipped without one.

## Running Tests

### With uv (Recommended)

```bash
# Unit tests (no API key needed, fast)
uv run pytest tests/test_basic.py -v
uv run pytest tests/test_field_configuration.py -v
uv run pytest tests/test_convenience_parameters.py -v
uv run pytest tests/test_security.py -v
uv run pytest tests/test_resilience.py -v

# Integration tests (requires API key, slower)
uv run pytest tests/test_integration.py -v
uv run pytest tests/test_statistics.py -v

# Cross-MCP integration tests
uv run pytest tests/test_unified_key_management.py -v

# Run all tests
uv run pytest tests/ -v

# Run specific test class
uv run pytest tests/test_integration.py::TestProgressiveDisclosureWorkflow -v

# Run with coverage
uv run pytest --cov=src/uspto_enriched_citation_mcp --cov-report=term-missing
```

### With traditional Python

```bash
# Unit tests
python -m pytest tests/test_basic.py -v
python -m pytest tests/test_field_configuration.py -v
python -m pytest tests/test_convenience_parameters.py -v

# Integration tests
python -m pytest tests/test_integration.py -v

# All tests
python -m pytest tests/ -v
```

### Direct Execution

```bash
# Run test file directly (for unified key management)
uv run python tests/test_unified_key_management.py
```

## Expected Results

### test_basic.py
```
test_basic.py::TestBasic::test_create_client PASSED
test_basic.py::TestBasic::test_client_initialization PASSED
test_basic.py::TestBasic::test_validate_query_syntax PASSED
test_basic.py::TestBasic::test_validate_empty_query PASSED
test_basic.py::TestBasic::test_get_fields PASSED
test_basic.py::TestBasic::test_search_records PASSED
test_basic.py::TestBasic::test_get_citation_details PASSED
test_basic.py::TestBasic::test_validate_boolean_query PASSED
test_basic.py::TestBasic::test_validate_range_query PASSED
test_basic.py::TestBasic::test_validate_wildcard_query PASSED
test_basic.py::TestBasic::test_validate_invalid_queries PASSED
test_basic.py::TestBasic::test_special_characters_in_query PASSED

======================== 12 passed in 1.0s ========================
```

### test_field_configuration.py
```
test_field_configuration.py::TestFieldManager::test_load_field_config PASSED
test_field_configuration.py::TestFieldManager::test_predefined_minimal_fields PASSED
test_field_configuration.py::TestFieldManager::test_predefined_balanced_fields PASSED
test_field_configuration.py::TestFieldManager::test_all_available_fields PASSED
test_field_configuration.py::TestFieldManager::test_field_filtering PASSED
test_field_configuration.py::TestFieldManager::test_invalid_field_rejection PASSED
test_field_configuration.py::TestFieldManager::test_field_validation PASSED
test_field_configuration.py::TestFieldManager::test_yaml_customization PASSED
test_field_configuration.py::TestFieldManager::test_field_set_descriptions PASSED
test_field_configuration.py::TestFieldManager::test_default_field_set PASSED
test_field_configuration.py::TestFieldManager::test_field_count_consistency PASSED
test_field_configuration.py::TestFieldFiltering::test_filter_single_document PASSED
test_field_configuration.py::TestFieldFiltering::test_filter_multiple_documents PASSED
test_field_configuration.py::TestFieldFiltering::test_filter_with_missing_fields PASSED
test_field_configuration.py::TestFieldFiltering::test_filter_preserves_values PASSED
test_field_configuration.py::TestFieldValidation::test_validate_all_valid_fields PASSED
test_field_configuration.py::TestFieldValidation::test_validate_with_invalid_fields PASSED
test_field_configuration.py::TestFieldValidation::test_validate_empty_list PASSED
test_field_configuration.py::TestFieldValidation::test_validate_mixed_fields PASSED

======================== 19 passed in 0.5s ========================
```

### test_convenience_parameters.py
```
test_convenience_parameters.py::TestConvenienceParameters::test_tech_center_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_applicant_name_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_application_number_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_patent_number_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_date_range_parameters PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_date_range_open_start PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_date_range_open_end PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_decision_type_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_category_code_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_examiner_cited_true PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_examiner_cited_false PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_art_unit_parameter PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_multiple_parameters PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_criteria_plus_parameters PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_no_colon_escaping PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_no_quote_escaping PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_no_bracket_escaping_in_ranges PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_no_dash_escaping_in_dates PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_parameter_validation_max_length PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_parameter_validation_invalid_chars PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_at_least_one_criterion_required PASSED
test_convenience_parameters.py::TestConvenienceParameters::test_field_name_constants_used PASSED
test_convenience_parameters.py::TestParameterEdgeCases::test_empty_string_parameters_ignored PASSED
test_convenience_parameters.py::TestParameterEdgeCases::test_whitespace_only_parameters_ignored PASSED
test_convenience_parameters.py::TestParameterEdgeCases::test_none_parameters_ignored PASSED
test_convenience_parameters.py::TestParameterEdgeCases::test_examiner_cited_none_ignored PASSED
test_convenience_parameters.py::TestParameterEdgeCases::test_date_validation_invalid_format PASSED

======================== 27 passed in 1.0s ========================
```

### test_security.py
```
test_security.py::TestSecurityLogger::test_security_logger_initialization PASSED
test_security.py::TestSecurityLogger::test_auth_success_logging PASSED
test_security.py::TestSecurityLogger::test_auth_failure_logging PASSED
test_security.py::TestSecurityLogger::test_query_validation_failure_logging PASSED
test_security.py::TestSecurityLogger::test_rate_limit_exceeded_logging PASSED
test_security.py::TestSecurityLogger::test_suspicious_pattern_logging PASSED
test_security.py::TestSecurityLogger::test_injection_attempt_logging PASSED
test_security.py::TestSecurityLogger::test_excessive_wildcards_logging PASSED
test_security.py::TestSecurityLogger::test_invalid_field_access_logging PASSED
test_security.py::TestSecurityLogger::test_api_access_logging PASSED
test_security.py::TestSecurityLogger::test_api_error_logging PASSED
test_security.py::TestSecurityLogger::test_query_sanitization PASSED
test_security.py::TestSecurityLogger::test_severity_level_mapping PASSED
test_security.py::TestSecurityLogger::test_global_security_logger_singleton PASSED
test_security.py::TestPromptInjectionDetection::test_instruction_override_detection PASSED
test_security.py::TestPromptInjectionDetection::test_prompt_extraction_detection PASSED
test_security.py::TestPromptInjectionDetection::test_unicode_steganography_detection PASSED
test_security.py::TestInputValidation::test_parameter_length_validation PASSED
test_security.py::TestInputValidation::test_special_character_handling PASSED
test_security.py::TestInputValidation::test_empty_input_handling PASSED
test_security.py::TestInputValidation::test_wildcard_limits PASSED
test_security.py::TestSecurityEventTypes::test_all_event_types_defined PASSED
test_security.py::TestSecurityEventTypes::test_event_type_values PASSED

======================== 23 passed in 1.5s ========================
```

### test_resilience.py
```
test_resilience.py::TestTokenBucket::test_token_bucket_initialization PASSED
test_resilience.py::TestTokenBucket::test_token_consumption_success PASSED
test_resilience.py::TestTokenBucket::test_token_consumption_failure PASSED
test_resilience.py::TestTokenBucket::test_token_replenishment PASSED
test_resilience.py::TestTokenBucket::test_token_capacity_limit PASSED
test_resilience.py::TestTokenBucket::test_wait_time_calculation PASSED
test_resilience.py::TestTokenBucket::test_async_wait_for_token PASSED
test_resilience.py::TestRateLimiter::test_rate_limiter_initialization PASSED
test_resilience.py::TestRateLimiter::test_rate_limit_allows_requests PASSED
test_resilience.py::TestRateLimiter::test_rate_limit_enforces_limit PASSED
test_resilience.py::TestRateLimiter::test_rate_limiter_singleton PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_breaker_initialization PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_allows_successful_calls PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_opens_on_failures PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_open_fails_fast PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_half_open_transition PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_closes_after_successes PASSED
test_resilience.py::TestCircuitBreaker::test_circuit_breaker_decorator PASSED
test_resilience.py::TestRetryLogic::test_backoff_calculation PASSED
test_resilience.py::TestRetryLogic::test_backoff_max_delay PASSED
test_resilience.py::TestRetryLogic::test_backoff_with_jitter PASSED
test_resilience.py::TestRetryLogic::test_retryable_error_detection PASSED
test_resilience.py::TestRetryLogic::test_retry_async_success_first_attempt PASSED
test_resilience.py::TestRetryLogic::test_retry_async_eventual_success PASSED
test_resilience.py::TestRetryLogic::test_retry_async_max_attempts PASSED
test_resilience.py::TestRetryLogic::test_retry_non_retryable_error PASSED
test_resilience.py::TestRetryLogic::test_retry_async_delay_increases PASSED
test_resilience.py::TestCaching::test_cache_key_generation PASSED
test_resilience.py::TestCaching::test_fields_cache PASSED
test_resilience.py::TestCaching::test_search_cache PASSED

======================== 30 passed in 2.5s ========================
```

### test_statistics.py
```
test_statistics.py::TestCitationStatistics::test_basic_statistics_retrieval PASSED
test_statistics.py::TestCitationStatistics::test_statistics_with_empty_criteria PASSED
test_statistics.py::TestCitationStatistics::test_category_distribution_stats PASSED
test_statistics.py::TestCitationStatistics::test_examiner_vs_applicant_stats PASSED
test_statistics.py::TestCitationStatistics::test_multiple_stats_fields PASSED
test_statistics.py::TestCitationStatistics::test_date_range_statistics PASSED
test_statistics.py::TestCitationStatistics::test_empty_result_statistics PASSED
test_statistics.py::TestCitationStatistics::test_invalid_stats_field PASSED
test_statistics.py::TestStatisticsServiceLayer::test_service_get_statistics PASSED
test_statistics.py::TestStatisticsServiceLayer::test_statistics_with_wildcard PASSED
test_statistics.py::TestStatisticsResponseFormat::test_response_has_required_fields PASSED
test_statistics.py::TestStatisticsResponseFormat::test_error_response_format PASSED
test_statistics.py::TestStatisticsResponseFormat::test_count_information PASSED
test_statistics.py::TestStatisticsPerformance::test_large_dataset_statistics PASSED
test_statistics.py::TestStatisticsPerformance::test_multiple_aggregations_performance PASSED
test_statistics.py::TestStatisticsEdgeCases::test_no_results_statistics PASSED
test_statistics.py::TestStatisticsEdgeCases::test_empty_stats_fields PASSED
test_statistics.py::TestStatisticsEdgeCases::test_complex_criteria_statistics PASSED
test_statistics.py::TestStatisticsEdgeCases::test_statistics_field_validation PASSED
test_statistics.py::TestStatisticsIntegration::test_statistics_with_field_manager PASSED
test_statistics.py::TestStatisticsIntegration::test_statistics_respects_api_constraints PASSED
test_statistics.py::TestStatisticsUseCase::test_art_unit_analysis PASSED
test_statistics.py::TestStatisticsUseCase::test_tech_center_comparison PASSED
test_statistics.py::TestStatisticsUseCase::test_temporal_analysis PASSED

======================== 24 passed in 12.0s =======================
```

### test_integration.py
```
test_integration.py::TestProgressiveDisclosureWorkflow::test_minimal_search_workflow PASSED
test_integration.py::TestProgressiveDisclosureWorkflow::test_balanced_search_workflow PASSED
test_integration.py::TestProgressiveDisclosureWorkflow::test_progressive_disclosure_sequence PASSED
test_integration.py::TestFieldManagementIntegration::test_get_available_fields PASSED
test_integration.py::TestFieldManagementIntegration::test_custom_field_search PASSED
test_integration.py::TestQuerySyntaxIntegration::test_basic_query_syntax PASSED
test_integration.py::TestQuerySyntaxIntegration::test_date_range_query PASSED
test_integration.py::TestConvenienceParametersIntegration::test_date_convenience_parameters PASSED
test_integration.py::TestCitationAnalysisIntegration::test_citation_category_analysis PASSED
test_integration.py::TestCitationAnalysisIntegration::test_examiner_vs_applicant_citations PASSED
test_integration.py::TestDateRangeIntegration::test_api_date_constraint PASSED
test_integration.py::TestDateRangeIntegration::test_date_range_validation PASSED
test_integration.py::TestErrorHandlingIntegration::test_empty_result_handling PASSED
test_integration.py::TestErrorHandlingIntegration::test_invalid_query_handling PASSED
test_integration.py::TestPerformanceIntegration::test_pagination_handling PASSED
test_integration.py::TestPerformanceIntegration::test_large_result_set_handling PASSED
test_integration.py::TestWorkflowIntegration::test_discovery_to_analysis_workflow PASSED
test_integration.py::TestWorkflowIntegration::test_tech_center_analysis_workflow PASSED

======================== 18 passed in 15.2s =======================
```

### test_unified_key_management.py
```
============================================================
USPTO MCP - Unified API Key Management Test
============================================================
[SECURITY] This test shows only the last 5 digits of API keys
============================================================

============================================================
Testing Unified Storage Functionality
============================================================
Storage paths:
  USPTO key:   C:\Users\<username>\.uspto_secure_keys\uspto_api_key
  Mistral key: C:\Users\<username>\.uspto_secure_keys\mistral_api_key
Platform:      Windows
DPAPI available: True

============================================================
Current API Key Status
============================================================
USPTO API Key:   ...eto (30 chars)
Mistral API Key: Not set

Available keys: USPTO_API_KEY

============================================================
Testing Key Storage & Retrieval
============================================================
1. Testing USPTO key storage...
   Store result: [OK] SUCCESS
   Retrieval:    [OK] SUCCESS (...67890 (40 chars))

2. Testing Mistral key storage...
   Store result: [OK] SUCCESS
   Retrieval:    [OK] SUCCESS (...54321 (32 chars))

3. Restoring original keys...
   Cleanup:      [OK] SUCCESS

============================================================
Test Summary
============================================================
Unified Storage:     [OK] Working
Key Storage/Retrieval: [OK] Working
Current USPTO Key:   [OK] Available
Current Mistral Key: [INFO]  Not set (optional)

[OK] Keys are configured. MCP should work properly.

[OK] Unified key management test completed successfully!
```

## Prerequisites

### Required Setup
- **Python 3.10+** with required dependencies installed
- **Internet connection** for USPTO API access
- **USPTO API Key** (see setup instructions below)

### Getting a USPTO API Key

1. Visit [USPTO Open Data Portal](https://data.uspto.gov/myodp/)
2. Register for an account - Select "I don't have a MyUSPTO account and need to create one"
3. Log in
4. Generate an API key for the Enriched Citation API
5. Set the key in your environment as shown above

**Security Note:** Never commit API keys to version control. Use secure DPAPI storage or environment variables.

## Key Features Tested

### Progressive Disclosure Pattern
- **Minimal search** (8 fields): Discovery mode, 90-95% context reduction
- **Balanced search** (18 fields): Analysis mode, 80-85% context reduction
- **Ultra-minimal custom** (2-3 fields): Maximum efficiency, 99% reduction
- **Complete details**: Full record with all 22 available fields

### Field Configuration System
- YAML-driven field customization (`field_configs.yaml`)
- No code changes required for field set modifications
- Predefined sets: `citations_minimal`, `citations_balanced`
- Custom fields parameter for ad-hoc ultra-minimal searches

### Convenience Parameters
- Tech center, art unit, application number, patent number
- Date range parameters (date_start, date_end)
- Citation category code filtering
- Examiner vs applicant citation filters
- Parameter validation and edge case handling

### Security Features
- Security event logging with structured fields
- Prompt injection pattern detection (70+ patterns)
- Unicode steganography detection
- Input validation and sanitization
- Rate limit exceeded logging
- Suspicious pattern detection
- Invalid field access tracking

### Resilience Features
- Token bucket rate limiting (default 100 req/min)
- Circuit breaker pattern (open/closed/half-open states)
- Retry logic with exponential backoff
- Response caching (LRU cache for fields and searches)
- Failure recovery and graceful degradation
- DoS attack prevention

### Statistics and Aggregations
- Citation category distribution analysis
- Examiner vs applicant citation statistics
- Tech center and art unit aggregations
- Date range temporal analysis
- Large dataset performance optimization

### Query Syntax Support
- Full Lucene syntax (boolean, wildcards, ranges, negation)
- Convenience parameters (no Lucene syntax required)
- Query validation and optimization suggestions
- Field-specific query types

### Citation Analysis
- Category filtering (X/Y/A/NPL)
- Examiner vs applicant citation distinction
- Passage location extraction
- Office action category analysis
- Strategic statistics and aggregations

### Date Range Handling
- API constraint: 2017-10-01 to 30 days before current date
- Filing-to-OA lag understanding (1-2 years)
- Date range query optimization
- Convenience date parameters

## Test Categories

### Core Functionality (Must Pass)
- Client initialization and configuration
- Field retrieval from API
- Query validation (Lucene syntax)
- Convenience parameter query building
- Field configuration system
- Security logging and event tracking
- Rate limiting enforcement
- Circuit breaker protection

### Critical Features (Must Pass)
- Progressive disclosure workflow
- Citation category analysis
- Statistics and aggregations
- API key validation and secure storage
- Context reduction efficiency
- Date constraint handling
- Prompt injection detection
- Retry logic with exponential backoff
- Response caching

### Enhancement Features (Should Pass)
- YAML field customization
- Advanced Lucene syntax
- Passage location analysis
- Custom statistics fields
- Pagination efficiency
- Cross-MCP key management

### Edge Cases (Should Pass)
- Empty result sets
- Special character escaping
- Boundary value testing
- Malformed input handling
- Invalid field rejection

## Performance Benchmarks

### Context Reduction Targets
- **Minimal**: ≥90% reduction (50 results ~2-5KB vs ~250KB raw)
- **Balanced**: ≥80% reduction (20 results ~8-10KB vs ~200KB raw)
- **Ultra-minimal**: ≥99% reduction (100 results ~1-2KB with 2-3 custom fields)

### Response Times
- Minimal search (50 rows): <2 seconds
- Balanced search (20 rows): <3 seconds
- Citation details: <1 second

### Accuracy
- Query validation: 100% syntax error detection
- Field validation: 100% invalid field rejection
- Date filtering: 100% constraint compliance

## Key Differences from Other USPTO MCPs

This MCP is unique in the USPTO MCP suite:

1. **Progressive Disclosure**: Only Citations MCP has minimal/balanced field tiers
2. **AI-Powered Data**: Citations use ML-extracted data from office actions
3. **Date Constraints**: Hard 2017-10-01 cutoff (other MCPs have different ranges)
4. **Field Customization**: YAML-driven configuration (others use code-based)
5. **Ultra-Minimal Mode**: Custom fields parameter for 99% token reduction
6. **No Examiner Names**: Use PFW MCP → Citations two-step workflow for examiner analysis

## Important API Limitations

### Available Fields (22 total as of 2024-07-11)
- Core: `citedDocumentIdentifier`, `patentApplicationNumber`, `publicationNumber`
- Citations: `citationCategoryCode`, `examinerCitedReferenceIndicator`
- Organizational: `groupArtUnitNumber`, `techCenter`, `workGroupNumber`
- Content: `passageLocationText`, `relatedClaimNumberText`, `officeActionCategory`

### Fields NOT Available
- ❌ `examinerNameText` (use PFW MCP workflow)
- ❌ `firstApplicantName`
- ❌ `decisionTypeCode` / `decisionTypeCodeDescriptionText`
- ❌ Classification fields (`uspcClassification`, `cpcClassificationBag`)

### Date Coverage
- Office actions: 2017-10-01 to 30 days prior to current date (hard API limit)
- For filing-date searches: Use 2015-01-01+ (accounts for lag to first OA)

## Troubleshooting

### Tests Skip with "API key not configured"
```bash
# Verify API key is set
# Windows Command Prompt
echo %USPTO_API_KEY%

# Windows PowerShell
echo $env:USPTO_API_KEY

# Linux/macOS
echo $USPTO_API_KEY
```

### ImportError or Module Not Found
```bash
# Ensure dependencies installed
uv sync

# Or reinstall
uv pip install -e .
```

### Integration Tests Fail
```bash
# Verify API key is valid
uv run python -c "from uspto_enriched_citation_mcp.config.settings import Settings; print(Settings().uspto_ecitation_api_key[:10] + '...')"

# Test API connectivity
uv run python -c "import httpx; r = httpx.get('https://developer.uspto.gov/ds-api'); print(r.status_code)"
```

### Field Count Mismatches
```bash
# Check current API field count
uv run python -c "from uspto_enriched_citation_mcp.main import initialize_services; import asyncio; s = asyncio.run(initialize_services()); print(len(s['field_manager'].get_fields('citations_minimal')))"
```

### Async Fixture Warnings
If you see pytest warnings about async fixtures, these are deprecation warnings from pytest-asyncio and don't affect test functionality. They will be addressed in future pytest versions.

## Documentation References

- **README.md**: End-user documentation and quick start
- **INSTALL.md**: Cross-platform installation guide
- **USAGE_EXAMPLES.md**: Function examples and workflows
- **PROMPTS.md**: Prompt template guide for citation analysis workflows
- **SECURITY_GUIDELINES.md**: Security best practices
- **field_configs.yaml**: Field configuration with inline comments
- **CLAUDE.md**: Development guide for Claude Code

## Test Development

When adding new tests:

1. **Unit tests** go in `test_basic.py` (mocked, fast)
2. **Integration tests** go in `test_integration.py` (real API)
3. **Configuration tests** go in `test_field_configuration.py`
4. **Convenience parameter tests** go in `test_convenience_parameters.py`
5. **Security tests** go in `test_security.py` (security logging, injection detection)
6. **Resilience tests** go in `test_resilience.py` (rate limiting, circuit breaker, retry)
7. **Statistics tests** go in `test_statistics.py` (aggregations, real API)
8. **Cross-MCP tests** go in `test_unified_key_management.py`

Follow the existing patterns:
- Use pytest fixtures for shared setup
- Use `@pytest.mark.asyncio` for async tests
- Skip integration tests gracefully if no API key
- Assert meaningful conditions, not just "not None"
- Document test purpose in docstrings

## Future Test Expansions

When cross-MCP integration is ready:
- PFW integration tests (examiner analysis 2-step workflow)
- PTAB correlation tests (citation patterns vs IPR success)
- FPD integration tests (petition citation analysis)
- Complete lifecycle tests (PFW → Citations → PTAB)
- Cross-MCP workflow validation
