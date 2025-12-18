# Security Guidelines

## Overview

This document provides comprehensive security guidelines for developing, deploying, and maintaining the USPTO Enriched Citation MCP Server. Following these guidelines helps ensure the security of API keys, user data, system integrity, and implementation of resilience patterns.

## API Key Management

### 🔐 **Environment Variables (Required)**

**Always use environment variables for API keys:**

```python
# ✅ Correct - Environment variable
import os
from .config.settings import get_required_env_var

api_key = get_required_env_var("USPTO_API_KEY")

# ❌ Never do this - Hardcoded key
api_key = "your_api_key_here"
```

### 🔑 **API Key Storage**

**Production Environment:**
```bash
# Set environment variables
export USPTO_API_KEY=your_api_key_here
export ECITATION_TIMEOUT=30.0
export ECITATION_RATE_LIMIT=100
export LOG_LEVEL=INFO
```

**Development Environment:**
```bash
# Use .env files (add to .gitignore)
echo "USPTO_API_KEY=your_dev_key" > .env
echo ".env" >> .gitignore
```

**Claude Desktop Configuration:**
```json
{
  "mcpServers": {
    "uspto_enriched_citation_mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/project", "run", "uspto-enriched-citation-mcp"],
      "env": {
        "USPTO_API_KEY": "your_api_key_here",
        "ECITATION_TIMEOUT": "30.0",
        "ECITATION_RATE_LIMIT": "100"
      }
    }
  }
}
```

### 🚫 **What Never to Commit**

- Real API keys in any form (especially USPTO API keys)
- Configuration files with real credentials
- Test files with hardcoded keys
- `.env` files or local config files
- Backup files that might contain keys
- API keys referenced in comments or documentation

## Code Security Patterns

### ✅ **Secure Patterns**

**1. Environment Variable Validation:**
```python
# src/uspto_enriched_citation_mcp/config/settings.py
import os
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

def get_required_env_var(key: str) -> str:
    """Get required environment variable with validation."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"{key} environment variable is required")
    if len(value) < 10:
        raise ValueError(f"{key} appears to be invalid (too short)")
    return value

class Settings(BaseSettings):
    uspto_api_key: str
    ecitation_timeout: float = 30.0
    ecitation_rate_limit: int = 100
    log_level: str = "INFO"
    
    def validate_api_key(self) -> bool:
        """Validate API key format."""
        if len(self.uspto_api_key) < 20:
            return False
        # Add additional validation as needed
        return True

# Usage in client
settings = Settings()
if not settings.validate_api_key():
    raise ValueError("Invalid USPTO API key format")
```

**2. Secure Authentication with Circuit Breaker:**
```python
# src/uspto_enriched_citation_mcp/api/enriched_client.py
from ..shared.circuit_breaker import uspto_api_breaker
from ..shared.error_utils import format_error_response

class EnrichedCitationClient:
    def __init__(self, api_key: str, base_url: str = "https://developer.uspto.gov/ds-api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",  # API key in header only
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=float(os.getenv("ECITATION_TIMEOUT", 30.0)),
        )

    @uspto_api_breaker
    async def get_fields(self) -> dict:
        """Get available fields with circuit breaker protection."""
        url = f"{self.base_url}/enriched_cited_reference_metadata/v3/fields"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise
```

**3. Request ID Tracking for Security:**
```python
# src/uspto_enriched_citation_mcp/shared/structured_logging.py
import uuid
import logging
from contextlib import contextmanager
from typing import Generator

@contextmanager
def request_context() -> Generator[str, None, None]:
    """Context manager for request tracking."""
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Request started")
    try:
        yield request_id
    except Exception as e:
        logger.error(f"[{request_id}] Request failed: {str(e)}")
        raise
    finally:
        logger.info(f"[{request_id}] Request completed")

# Usage
async def search_citations(criteria: str):
    async with request_context() as request_id:
        logger.info(f"[{request_id}] Processing citation search")
        # Your code here
```

### ❌ **Anti-Patterns to Avoid**

**1. Hardcoded Secrets:**
```python
# NEVER DO THIS
API_KEY = "your_api_key_here"  # ❌
```

**2. Secrets in Comments:**
```python
# Don't include real keys in comments
# My key is: your_api_key_here  # ❌
```

**3. Logging Secrets:**
```python
# Never log API keys
logger.info(f"Using API key: {api_key}")  # ❌
logger.info(f"Using API key: {api_key[:4]}***")  # ✅ Safe
```

**4. Error Messages Exposing Secrets:**
```python
# ❌ Exposes internal information and potentially API keys
return f"Failed to authenticate with key {self.api_key} against {self.base_url}"

# ✅ Safe error message
return format_error_response("Authentication failed - check API key configuration", 401, request_id)
```

## Error Handling Security

### 🛡️ **Secure Error Responses**

```python
# src/uspto_enriched_citation_mcp/shared/error_utils.py
def format_error_response(
    message: str, 
    code: int = 500, 
    request_id: str = None,
    include_details: bool = False
) -> dict:
    """Format error without exposing sensitive data."""
    response = {
        "status": "error",
        "error": message,  # User-friendly message only
        "code": code,
        "message": message
    }
    if request_id:
        response["request_id"] = request_id
    
    # Only include internal details in development
    if include_details and os.getenv("LOG_LEVEL") == "DEBUG":
        response["debug_info"] = "Additional debugging information available"
    
    return response

# Safe logging without secret exposure
def log_api_error(error: Exception, request_id: str, api_endpoint: str):
    """Log API errors without exposing secrets."""
    error_type = type(error).__name__
    logger.error(f"[{request_id}] {error_type} on {api_endpoint}: {str(error)}")
    # Never log API keys, headers with auth, or full request URLs with auth
```

### 🚨 **Information Disclosure Prevention**

**Safe message examples:**
```python
# ✅ Safe error messages
"Authentication failed - check API key configuration"
"API request timed out - please try again later"
"Invalid query syntax - use validate_query tool for help"
"Citation service temporarily unavailable"

# ❌ Exposes internal information
f"Failed to authenticate with key {api_key} against {internal_url}"
f"Database connection failed: {connection_string}"
"Circuit breaker opened after {failure_count} failures with {threshold} threshold"
```

## File and Repository Security

### 📁 **.gitignore Requirements**

```gitignore
# API Keys and Secrets
*api_key*
*API_KEY*
*.key
secrets.json
.env
.env.local
.env.production
.env.dev
*.env.*

# Configuration files with secrets
*local*.json
*_with_keys*
*_secrets*
config_real.json
config_production.json

# Logs and debug files
*.log
debug.log
error.log
api_requests.log

# Python
__pycache__/
*.pyc
.env
.venv/
venv/
env/

# Dependency files (can contain sensitive package versions)
uv.lock
package-lock.json
Pipfile.lock

# Claude Code integration
.claude/

# Backup files
*.bak
*.backup
*~
```

### 🗂️ **Configuration Templates**

**Template files should use empty placeholders:**
```json
// configs/example_claude_desktop.json
{
  "mcpServers": {
    "uspto_enriched_citation_mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/uspto_enriched_citation_mcp", "run", "uspto-enriched-citation-mcp"],
      "env": {
        "USPTO_API_KEY": "",
        "ECITATION_TIMEOUT": "30.0",
        "ECITATION_RATE_LIMIT": "100",
        "LOG_LEVEL": "INFO"
      },
      "documentation": {
        "USPTO_API_KEY": "Get from https://data.uspto.gov/myodp/",
        "other_fields": "Defaults provided for optimal performance"
      }
    }
  }
}
```

## Resilience and Circuit Breaker Security

### 🔌 **Circuit Breaker Implementation**

**Secure Circuit Breaker Usage:**
```python
from .shared.circuit_breaker import CircuitBreaker, uspto_api_breaker

# Use pre-configured breaker for all USPTO API calls
@uspto_api_breaker
async def secure_api_call(endpoint: str, data: dict = None):
    """API call with circuit breaker protection."""
    try:
        response = await self.client.post(endpoint, data=data)
        response.raise_for_status()
        return response.json()
    except CircuitBreakerError:
        logger.error("Circuit breaker is OPEN - API temporarily unavailable")
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("API authentication failed - check API key")
        raise

# Custom circuit breaker for critical operations
@custom_breaker = circuit_breaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    success_threshold=2,
    expected_exception=(ConnectionError, TimeoutError, httpx.HTTPError)
)
```

**Monitoring Circuit Health:**
```python
def monitor_circuit_health(breaker: CircuitBreaker):
    """Monitor and log circuit breaker state."""
    state = breaker.state
    failures = breaker.failure_count
    
    if state == CircuitState.OPEN:
        logger.warning(f"🔴 Circuit OPEN - {failures} failures recorded")
        # Implement notification for operations team
        notify_operations("USPTO API circuit breaker OPEN")
    elif state == CircuitState.HALF_OPEN:
        logger.warning(f"🟡 Circuit HALF-OPEN - testing recovery")
    else:
        logger.debug(f"🟢 Circuit CLOSED - {failures} recent failures")
```

### 🛡️ **Rate Limiting Security**

```python
# src/uspto_enriched_citation_mcp/config/settings.py
class Settings(BaseSettings):
    ecitation_rate_limit: int = 100  # USPTO API limit
    
    def validate_rate_limit(self) -> bool:
        """Ensure rate limit is within safe bounds."""
        if self.ecitation_rate_limit > 1000:
            logger.warning("Rate limit set very high - may trigger API abuse detection")
        return 0 < self.ecitation_rate_limit <= 1000

# In client - implement rate limiting
import asyncio
from asyncio import Semaphore

class RateLimitedClient:
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self.semaphore = Semaphore(rate_limit // 10)  # Rough rate limiting
        
    async def make_request(self, func, *args, **kwargs):
        async with self.semaphore:
            return await func(*args, **kwargs)
```

## Development Workflow Security

### 🔒 **Secure Development Process**

1. **Before Coding:**
   - Set up `.gitignore` before first commit
   - Install pre-commit hooks immediately
   - Set environment variables for development

2. **During Development:**
   - Use test keys or placeholder values for development
   - Implement proper error handling with request IDs
   - Add circuit breaker patterns to all external API calls
   - Test failure scenarios

3. **Before Committing:**
   - Run security scan: `uv run pre-commit run --all-files`
   - Verify no hardcoded secrets
   - Test with environment variables
   - Check error messages don't expose internals

4. **Before Publishing:**
   - Full security audit of codebase
   - Clean git history if needed
   - Verify all configuration templates
   - Test circuit breaker scenarios

### 🧪 **Testing Security**

```python
# tests/test_security.py
def test_no_hardcoded_secrets():
    """Ensure no hardcoded API keys in codebase."""
    import subprocess
    import os
    
    # Search for potential hardcoded keys
    result = subprocess.run([
        'grep', '-rE', 'USPTO_API_KEY.*=.*"[A-Za-z0-9]{20,}"',
        '.', '--exclude-dir=.git', '--exclude-dir=.venv', 
        '--include=*.py', '--include=*.md', '--include=*.json'
    ], capture_output=True, text=True)

    assert result.returncode != 0, "Found hardcoded API key in codebase"

def test_circuit_breaker_protection():
    """Test circuit breaker prevents cascade failures."""
    from src.uspto_enriched_citation_mcp.shared.circuit_breaker import uspto_api_breaker
    
    # Circuit should start closed
    assert uspto_api_breaker.state.name == "CLOSED"
    
    # Test circuit breaker behavior
    async def failing_call():
        raise ConnectionError("Simulated failure")
    
    # Trigger failures to open circuit
    for _ in range(6):  # Exceed default threshold of 5
        try:
            await uspto_api_breaker.call(failing_call)
        except:
            pass
    
    # Circuit should be open now
    assert uspto_api_breaker.state.name == "OPEN"
```

## Incident Response

### 🚨 **If API Key is Exposed**

**Immediate Actions (within 1 hour):**
1. **Invalidate the exposed key** at USPTO developer portal immediately
2. **Generate new API key** from USPTO Data Services
3. **Update production environment** with new key
4. **Check USPTO API logs** for unauthorized usage

**Cleanup Actions (within 24 hours):**
1. **Remove from git history** if committed:
   ```bash
   # Use BFG Repo Cleaner for complete removal
   java -jar bfg.jar --replace-text <secrets.txt> repo.git
   git push --force
   ```
2. **Update all team members** with new key
3. **Review access logs** for suspicious activity
4. **Implement additional monitoring** for the new key
5. **Create post-mortem** and improve processes

### 📋 **Response Checklist**

- [ ] API key invalidated at source (USPTO Portal)
- [ ] New key generated and deployed
- [ ] Git history cleaned (if needed)
- [ ] Team notified of key change
- [ ] Monitoring implemented for new key
- [ ] Circuit breaker behavior verified
- [ ] Security scan baseline updated
- [ ] Post-mortem completed
- [ ] Process improvements identified

### 🔌 **Circuit Breaker Incidents**

**If Circuit Breaker Opens Frequently:**
1. **Check API rate limit usage** - may need to reduce request rate
2. **Verify API endpoint availability** - USPTO service may be down
3. **Network connectivity issues** - check DNS/firewall
4. **Authentication problems** - API key may have been revoked
5. **Review request patterns** - may have inefficient queries

## Monitoring and Auditing

### 📊 **Security Monitoring**

```python
# Security-relevant logging
def log_security_event(event_type: str, request_id: str, details: dict = None):
    """Log security events with proper context."""
    logger.info(f"[{request_id}] SECURITY_EVENT: {event_type}")
    if details:
        for key, value in details.items():
            logger.debug(f"[{request_id}] {key}: {redact_sensitive_data(value)}")

def redact_sensitive_data(data: str) -> str:
    """Redact potential sensitive data from logs."""
    if len(data) > 20 and any(char.isalnum() for char in data):
        return data[:4] + "*" * (len(data) - 8) + data[-4:] if len(data) >= 8 else "*" * len(data)
    return data

# Examples
log_security_event("API_AUTH_SUCCESS", request_id)
log_security_event("CIRCUIT_BREAKER_OPENED", request_id, {"failure_count": failure_count})
log_security_event("RATE_LIMIT_WARNING", request_id, {"current_rate": rate})
```

### 🔍 **Regular Security Audits**

**Weekly Checklist:**
- [ ] Run `uv run pre-commit run --all-files`
- [ ] Check GitHub Actions security scan results
- [ ] Review circuit breaker opening events
- [ ] Verify .gitignore effectiveness
- [ ] Check for new vulnerabilities in dependencies

**Monthly Checklist:**
- [ ] Full security scan of codebase for hardcoded secrets
- [ ] Review API key rotation schedule  
- [ ] Audit access logs for suspicious patterns
- [ ] Test circuit breaker scenarios
- [ ] Review error message exposure
- [ ] Update team on security practices

## Tools and Automation

### 🔧 **Security Tools Configuration**

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: '.venv*|uv.lock'

  - repo: local
    hooks:
      - id: python-tests
        name: Run tests
        entry: uv run python -m pytest tests/ -v
        language: system
        pass_filenames: false
        always_run: true

      - id: lint-quality
        name: Code quality with security focus
        entry: uv run python -m bandit -r src/ -f json -o bandit-report.json
        language: system
        pass_filenames: false
        always_run: true
```

**Automated Security Scripts:**
```bash
#!/bin/bash
# scripts/security-check.sh
echo "🔒 Running comprehensive security check..."

echo "🔍 Scanning for hardcoded secrets..."
if grep -rE 'USPTO_API_KEY.*=.*"[A-Za-z0-9]{20,}"' . --exclude-dir=.git --exclude-dir=.venv --include="*.py" --include="*.md"; then
    echo "❌ Found potential hardcoded API key"
    exit 1
fi

echo "🛡️ Running bandit security analysis..."
uv run bandit -r src/ -f json -o bandit-report.json
HIGH_ISSUES=$(python -c "import json; print(len([r for r in json.load(open('bandit-report.json')).get('results', []) if r['issue_severity']=='HIGH']))")
if [ "$HIGH_ISSUES" -gt 0 ]; then
    echo "❌ Found $HIGH_ISSUES high-severity security issues"
    exit 1
fi

echo "🔒 Testing circuit breaker configuration..."
uv run python -c "
from src.uspto_enriched_citation_mcp.shared.circuit_breaker import uspto_api_breaker
print('✅ Circuit breaker configured:', uspto_api_breaker.state.name)
"

echo "✅ Security check completed successfully"
```

## Compliance and Best Practices

### 📋 **Security Compliance**

**OWASP Top 10 Alignment:**
- **A07:2021 – Identification and Authentication Failures**: Environment variables, circuit breaker protection, API key validation
- **A04:2021 – Insecure Design**: Secure patterns, error handling without information disclosure
- **A05:2021 – Security Misconfiguration**: Proper .gitignore, templates, rate limiting
- **A01:2021 – Broken Access Control**: Circuit breaker prevents unauthorized API access during failures
- **A09:2021 – Security Logging and Monitoring Failures**: Request ID tracking, security event logging

**Industry Best Practices:**
- Environment variables for all secrets
- Circuit breaker patterns for resilience
- Comprehensive error handling without information disclosure
- Regular security scanning (detect-secrets, bandit, safety)
- Proper incident response procedures
- Security monitoring and logging

## Training and Awareness

### 📚 **Developer Training Topics**

1. **API Key Management**
   - Environment variables vs hardcoding dangers
   - USPTO API key protection requirements
   - Key rotation and incident procedures

2. **Secure Coding Patterns**
   - Input validation for Lucene queries
   - Error handling without information disclosure
   - Circuit breaker implementation

3. **Repository Security**
   - .gitignore configuration
   - Pre-commit hook usage
   - Secret scanning workflows

4. **Resilience Patterns**
   - Circuit breaker concepts and usage
   - Rate limiting implementation
   - Fallback mechanisms

### ✅ **Security Checklist for Developers**

Before each commit:
- [ ] No hardcoded USPTO API keys
- [ ] Environment variables used correctly
- [ ] Error messages don't expose secrets
- [ ] .gitignore includes sensitive patterns
- [ ] Test files use secure patterns
- [ ] Circuit breaker applied to external calls
- [ ] Request IDs used for logging

Before each release:
- [ ] Full security scan completed (detect-secrets, bandit)
- [ ] All configuration templates secured
- [ ] Documentation updated with security practices
- [ ] Circuit breaker scenarios tested
- [ ] Team trained on changes

## Conclusion

Security is everyone's responsibility. For the USPTO Enriched Citation MCP, this means:
1. **Protecting API keys** through environment variables and secret scanning
2. **Ensuring system resilience** through circuit breaker patterns
3. **Preventing information disclosure** through secure error handling
4. **Maintaining audit trails** through request ID tracking
5. **Regular security monitoring** through automated scanning

By following these guidelines and implementing the security features (circuit breaker, secret scanning, structured logging), we ensure that the USPTO Enriched Citation MCP Server remains secure, resilient, and trustworthy for users conducting patent research and analysis.

For questions about security practices or to report security issues, contact the project maintainers immediately.

**Critical Security Contacts:**
- **API Key Issues**: Regenerate at [USPTO Data Services Portal](https://data.uspto.gov/myodp/)
- **Code Security**: File GitHub issue with "SECURITY" label
- **Incident Response**: Follow response checklist above