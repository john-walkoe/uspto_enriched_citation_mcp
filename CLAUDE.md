# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Core Development Workflow

```bash
# Install dependencies and setup virtual environment
uv sync

# Run the MCP server for testing
uv run uspto-enriched-citation-mcp

# Alternative execution methods
uv run python -m uspto_enriched_citation_mcp
uv run python src/uspto_enriched_citation_mcp/main.py
```

### Testing Commands

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/test_basic.py -v                    # Unit tests (no API key needed)
uv run pytest tests/test_integration.py -v             # Integration tests (API key required)
uv run pytest tests/test_security.py -v                # Security tests
uv run pytest tests/test_resilience.py -v              # Circuit breaker, rate limiting
uv run pytest tests/test_field_configuration.py -v     # Field management
uv run pytest tests/test_statistics.py -v              # Citation statistics

# Run tests with coverage
uv run pytest --cov=src/uspto_enriched_citation_mcp --cov-report=term-missing

# Run specific test
uv run pytest tests/test_basic.py::TestBasic::test_create_client -v
```

### Code Quality and Security

```bash
# Run security scans (as defined in CI/CD)
uv run detect-secrets scan --exclude-files '.venv*' --all-files

# Run code quality checks
uv run pre-commit run --all-files

# Type checking
uv run mypy src/

# Code formatting
uv run black src/ tests/
uv run ruff check src/ tests/
```

### API Key Management

```bash
# Test API key configuration (Windows DPAPI or environment variables)
uv run python tests/test_unified_key_management.py

# Check current API key status (last 4 digits only)
uv run python -c "from uspto_enriched_citation_mcp.shared.shared_secure_storage import get_api_key; print('Key present' if get_api_key('USPTO_API_KEY') else 'No key')"
```

## Architecture Overview

### High-Level Architecture

This is a **Model Context Protocol (MCP) server** that provides structured access to the USPTO Enriched Citation API v3. The architecture follows a **progressive disclosure pattern** with multiple tiers of data detail to optimize token usage and API efficiency.

### Core Design Patterns

1. **Progressive Disclosure Workflow**
   - `minimal` search (8 fields, 90-95% context reduction) → discovery phase
   - `balanced` search (18 fields, 80-85% context reduction) → analysis phase  
   - `ultra-minimal` custom fields (2-3 fields, 99% reduction) → integration phase
   - `detailed` individual records → deep analysis phase

2. **Field Configuration System**
   - YAML-driven field customization via `field_configs.yaml`
   - No code changes required for field set modifications
   - Predefined sets: `citations_minimal`, `citations_balanced`

3. **Service Layer Architecture**
   ```
   MCP Tools (main.py) → Service Layer (citation_service.py) → API Client (enriched_client.py) → USPTO API
   ```

### Tool Search Optimization

**Status**: Enabled in Claude Code v2.1.7+ (built-in, automatic)

Citations MCP supports tool search for context efficiency:
- **Token Savings**: 50-60% reduction in tool definition overhead (~3-5K tokens saved)
- **Auto-detection**: When MCP tools exceed 10% of context, tool search activates automatically
- **Entry Points**: `search_citations_minimal` and `citations_get_guidance` always available
- **Progressive Discovery**: Other tools loaded on-demand via MCPSearch

To verify tool search is working:
```bash
# Run in Claude Code CLI
/context
# Should show: "MCP tools: loaded on-demand (N servers)"
```

To enable manually (if needed):
```bash
# Windows PowerShell
$env:ENABLE_TOOL_SEARCH = "true"
claude

# Linux/Mac
export ENABLE_TOOL_SEARCH=true
claude
```

### Key Components

#### `/src/uspto_enriched_citation_mcp/`

**Main MCP Server (`main.py`)**
- FastMCP server with 6 core tools
- Progressive disclosure tools: `search_citations_minimal`, `search_citations_balanced`
- Analysis tools: `get_citation_details`, `get_citation_statistics`
- Utility tools: `get_available_fields`, `validate_query`, `citations_get_guidance`
- Query building with Lucene syntax support and convenience parameters

**API Layer (`/api/`)**
- `enriched_client.py`: Modern httpx-based client with circuit breaker, rate limiting, caching
- `client.py`: Deprecated aiohttp-based client (will be removed in v2.0)
- `field_constants.py`: Field definitions and constants

**Configuration (`/config/`)**
- `settings.py`: Environment-based configuration using Pydantic
- `field_manager.py`: YAML-based field configuration management
- `feature_flags.py`: Feature flag system
- `secure_storage.py`: Windows DPAPI encryption for API keys

**Services (`/services/`)**
- `citation_service.py`: Business logic layer for citation operations
- Handles cross-MCP integration logic and response formatting

**Shared Utilities (`/shared/`)**
- `circuit_breaker.py`: Circuit breaker pattern implementation
- `structured_logging.py`: Enhanced logging with request tracking
- `error_utils.py`: Standardized error handling and formatting
- `exceptions.py`: Custom exception classes

**Utilities (`/util/`)**
- `rate_limiter.py`: Token bucket rate limiting algorithm  
- `retry.py`: Exponential backoff retry logic
- `cache.py`: LRU caching for API responses
- `security_logger.py`: Security event logging and prompt injection detection

**Prompt Templates (`/prompts/`)**
- Sophisticated multi-step analysis workflows
- Cross-MCP integration templates
- Patent research and litigation analysis prompts

### Configuration Files

**Field Configuration (`field_configs.yaml`)**
- Defines minimal and balanced field sets
- User-customizable without code changes
- Comments explain cross-MCP integration fields

**Feature Flags (`feature_flags.example.conf`)**
- Runtime feature toggles
- Development and production environment controls

### Security Architecture

1. **API Key Management**
   - Windows: DPAPI encryption (user+machine specific)
   - Unix: File permissions (600) with environment variable fallback
   - Unified storage across all USPTO MCPs

2. **Input Validation & Security**
   - Lucene query syntax validation
   - Parameter length and character restrictions  
   - Prompt injection detection (70+ patterns)
   - Security event logging with request tracking

3. **Rate Limiting & Circuit Breaking**
   - Token bucket algorithm (default: 100 req/min)
   - Circuit breaker with open/closed/half-open states
   - Exponential backoff retry logic

### Cross-MCP Integration

Designed to work with other USPTO MCP servers:
- **USPTO Patent File Wrapper (PFW)**: Prosecution history integration
- **USPTO PTAB**: Post-grant challenge correlation  
- **USPTO Final Petition Decisions (FPD)**: Petition analysis
- **Pinecone Assistant**: Patent law knowledge base

Integration pattern: Citations → Application Numbers → PFW → Documents

### Testing Architecture

**Test Categories:**
- **Unit Tests** (`test_basic.py`, `test_field_configuration.py`, etc.): Fast, no API key required
- **Integration Tests** (`test_integration.py`, `test_statistics.py`): Real API calls, requires USPTO key
- **Security Tests** (`test_security.py`): Injection detection, input validation
- **Resilience Tests** (`test_resilience.py`): Circuit breaker, rate limiting, caching

### Development Patterns

1. **Lazy Initialization**: Services initialized on first use
2. **Request Context**: Request ID tracking throughout call chain  
3. **Structured Logging**: JSON logs to stderr (not stdout for MCP compatibility)
4. **Error Handling**: Standardized error responses with context
5. **Caching Strategy**: Fields cache (TTL) + search cache (LRU)

### Performance Characteristics

- **Context Reduction**: 90-99% reduction vs raw API responses
- **Rate Limits**: 100 requests/minute default (configurable)  
- **Timeouts**: 30 second default API timeout
- **Caching**: 10-minute field cache, 100-entry search cache

### Important Constraints

1. **API Data Coverage**: Office actions from 2017-10-01 forward only
2. **Field Limitations**: 22 total fields available (examiner names NOT in citation API)
3. **Metadata Only**: Returns citation data, not actual documents (use PFW MCP for documents)
4. **Cross-MCP Workflows**: Required for examiner analysis (PFW → Citations)

### Deployment Notes

- Uses `uv` package manager for dependency management
- Supports Windows (DPAPI), Linux/macOS (file permissions)
- Claude Desktop/Code integration via MCP protocol
- GitHub Actions CI/CD with comprehensive security scanning