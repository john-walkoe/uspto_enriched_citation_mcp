# Environment-Based Configuration

This project supports multiple deployment environments with pre-configured settings optimized for each use case.

## Available Environments

### 1. Development
**Purpose**: Local development and debugging

**Characteristics:**
- **Verbose logging** (DEBUG level)
- **Relaxed rate limits** (200 req/min, rate limiting disabled)
- **Longer timeouts** (60s API, 30s connect)
- **Circuit breaker disabled** (easier debugging)
- **Verbose errors** (full stack traces)
- **Experimental features enabled**
- **Fast cache refresh** (1 minute TTL)

**Best for:** Active development, debugging, testing new features

### 2. Staging
**Purpose**: Pre-production testing with production-like settings

**Characteristics:**
- **INFO logging** with detailed logs
- **Production rate limits** (100 req/min, enabled)
- **Production timeouts** (30s API, 10s connect)
- **All resilience features enabled**
- **Verbose errors** (for debugging)
- **Beta features enabled** (test before production)
- **Moderate cache refresh** (30 minutes TTL)

**Best for:** Integration testing, QA, pre-release validation

### 3. Production
**Purpose**: Live deployment optimized for performance and stability

**Characteristics:**
- **INFO logging** (minimal overhead)
- **Standard rate limits** (100 req/min, enabled)
- **Optimized timeouts** (30s API, 10s connect)
- **All resilience features enabled**
- **User-friendly errors** (no internal details)
- **Experimental features disabled**
- **Stable cache** (1 hour TTL)

**Best for:** Live production deployments

### 4. Testing
**Purpose**: Automated test suites

**Characteristics:**
- **WARNING logging** (reduce noise)
- **No caching** (deterministic tests)
- **High rate limits** (1000 req/min, disabled)
- **Short timeouts** (5s API, 2s connect)
- **Resilience disabled** (predictable behavior)
- **Verbose errors** (test debugging)
- **No experimental features**

**Best for:** pytest, integration tests, CI/CD

## Quick Start

### Option 1: Environment Variable (Recommended)

```bash
# Set environment
export APP_ENV=development  # or staging, production, testing

# Run application
uv run python -m uspto_enriched_citation_mcp
```

Supported values: `development`, `dev`, `staging`, `stage`, `production`, `prod`, `testing`, `test`

### Option 2: Environment-Specific .env Files

1. **Copy the appropriate template:**
```bash
# Development
cp .env.development.example .env

# Staging
cp .env.staging.example .env

# Production
cp .env.production.example .env
```

2. **Update the API key:**
```bash
# Edit .env
USPTO_ECITATION_API_KEY=your_actual_api_key_here
```

3. **Run application:**
```bash
uv run python -m uspto_enriched_citation_mcp
```

## Configuration Priority

Settings are loaded in this order (highest to lowest priority):

1. **Environment variables** (e.g., `ENABLE_CACHE=false`)
2. **Feature flags file** (`feature_flags.conf`)
3. **Environment-specific .env file** (`.env`)
4. **Environment defaults** (from `environments.py`)
5. **Application defaults** (from `settings.py`)

### Example: Override Caching in Production

```bash
# Method 1: Environment variable
export ENABLE_CACHE=false

# Method 2: Feature flags file
echo "enable_fields_cache=false" >> feature_flags.conf

# Method 3: .env file
echo "ENABLE_CACHE=false" >> .env
```

## Environment-Specific Settings

### Development Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `LOG_LEVEL` | DEBUG | See all internal operations |
| `ENABLE_RATE_LIMITING` | false | No throttling during development |
| `ENABLE_CIRCUIT_BREAKER` | false | See all API failures directly |
| `API_TIMEOUT` | 60s | Time to debug slow requests |
| `FIELDS_CACHE_TTL` | 60s | Fast refresh for API changes |
| `ENABLE_VERBOSE_ERRORS` | true | Full error details |

### Staging Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `LOG_LEVEL` | INFO | Production-like logging |
| `ENABLE_RATE_LIMITING` | true | Test rate limit behavior |
| `ENABLE_CIRCUIT_BREAKER` | true | Test resilience features |
| `ENABLE_BETA_FEATURES` | true | Test new features safely |
| `ENABLE_VERBOSE_ERRORS` | true | Debugging pre-production issues |

### Production Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `LOG_LEVEL` | INFO | Balance observability/performance |
| `ENABLE_RATE_LIMITING` | true | Protect API quota |
| `ENABLE_CIRCUIT_BREAKER` | true | Prevent cascade failures |
| `ENABLE_BETA_FEATURES` | false | Stability first |
| `ENABLE_VERBOSE_ERRORS` | false | Hide internal details |

## Programmatic Environment Detection

The environment is automatically detected from the `APP_ENV` or `ENVIRONMENT` environment variable:

```python
from .config.environments import get_environment, get_environment_config

# Get current environment
env = get_environment()  # Returns Environment.DEVELOPMENT, etc.

# Get configuration for current environment
config = get_environment_config()

# Apply configuration
config_dict = config.to_dict()
```

## Custom Environment Configuration

To create a custom environment:

```python
from .config.environments import EnvironmentConfig

custom_config = EnvironmentConfig(
    name="custom",
    description="My custom environment",
    log_level="INFO",
    enable_cache=True,
    # ... other settings
)
```

## Troubleshooting

### Environment Not Detected
```bash
# Check environment variable
echo $APP_ENV

# If empty, set it
export APP_ENV=development
```

### Configuration Not Applied
```bash
# Check priority order:
# 1. Environment variables override everything
# 2. Feature flags override .env
# 3. .env overrides defaults

# Debug: Enable detailed logging
export LOG_LEVEL=DEBUG
```

### Cache Not Clearing Between Tests
```bash
# Use testing environment (disables cache)
export APP_ENV=testing

# Or manually disable
export ENABLE_CACHE=false
```

## Best Practices

1. **Use `.env` files for local development** - Easy to switch between configs
2. **Use environment variables in CI/CD** - Single source of truth
3. **Use feature flags for runtime toggles** - No restart required
4. **Test with staging first** - Validate before production
5. **Monitor production carefully** - Watch for environment-specific issues

## See Also

- **Feature Flags**: `feature_flags.example.conf`
- **Settings**: `src/uspto_enriched_citation_mcp/config/settings.py`
- **Environments**: `src/uspto_enriched_citation_mcp/config/environments.py`
