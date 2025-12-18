# Naming Convention Guide & Remediation - USPTO Enriched Citation MCP

**Version:** 1.0  
**Date:** 2025-11-08  
**Scope:** Practical implementation guide for naming standards and code improvements  

## Table of Contents
1. [Quick Reference](#quick-reference)
2. [Detailed Standards](#detailed-standards)
3. [Before/After Examples](#before-after-examples)
4. [Automated Tools](#automated-tools)
5. [Step-by-Step Remediation](#step-by-step-remediation)
6. [Code Review Checklist](#code-review-checklist)

---

## Quick Reference

### Naming Conventions Cheat Sheet

| Element | Convention | Example | Bad Example |
|---------|------------|---------|-------------|
| **Variables** | snake_case | `patent_application_number` | `patentAppNum`, `PATENT_APPLICATION_NUMBER` |
| **Constants** | UPPER_SNAKE_CASE | `MAX_SEARCH_RESULTS` | `maxSearchResults`, `max_search_results` |
| **Functions** | snake_case | `get_citation_details()` | `getCitationDetails()`, `GetCitationDetails()` |
| **Classes** | PascalCase | `CitationService` | `citationService`, `citation_service` |
| **Private Methods** | _leading_underscore | `_validate_query()` | `validateQuery()`, `ValidateQuery()` |
| **Parameters** | snake_case | `application_number: str` | `appNum: str`, `AppNumber: str` |
| **Module Files** | snake_case | `citation_service.py` | `citationService.py`, `CitationService.py` |

### Critical Rules Summary
- **ALWAYS use snake_case for Python identifiers** (variables, functions, parameters)
- **ALWAYS use UPPER_SNAKE_CASE for constants**
- **ALWAYS use PascalCase for classes**
- **NEVER mix case conventions in the same scope**
- **AVOID abbreviations unless universally known (e.g., `api`, `id`, `url`)**

---

## Detailed Standards

### 1. Variable Naming Standards

#### ✅ Good Examples
```python
# Domain-specific variables
patent_application_number = "18010777"
citation_category_code = "X"
examiner_cited_reference = True
office_action_date = "2023-12-15"

# API-related variables
api_response_data = {}
http_request_headers = {"Content-Type": "application/json"}
validation_result = True

# Collection variables (descriptive plural)
patent_applications = []
citation_records = []
valid_field_names = {}

# Boolean variables (positive, clear)
has_citation_data = True
is_valid_patent_number = False
should_include_context = True
can_make_api_call = True
```

#### ❌ Bad Examples
```python
# Mixed case (NEVER DO THIS)
patentAppNum = "18010777"  # camelCase in snake_case context
citation_cat = "X"         # unclear abbreviation

# Constants in wrong case
max_results = 100          # Should be MAX_RESULTS
api_key = "secret"         # Should be API_KEY or api_key

# Unclear boolean names
flag = True                # What does flag mean?
check = False              # Check what?
valid = True               # Valid what?
```

#### Variable Naming Rules
1. **Use descriptive names** that explain the variable's purpose
2. **Include domain context** for patent/legal terms
3. **Use plural forms** for collections (`patent_applications`, not `patent_application_list`)
4. **Boolean variables should be positive** (`is_valid`, `has_data`, `can_process`)
5. **Avoid single letters** except in very limited scopes (loop counters, mathematical expressions)

### 2. Constant Naming Standards

#### ✅ Good Examples
```python
# API Configuration
USPTO_API_BASE_URL = "https://developer.uspto.gov/ds-api"
USPTO_API_TIMEOUT_SECONDS = 30
MAX_CITATION_RECORDS_PER_REQUEST = 1000

# Search Limits
MAX_MINIMAL_SEARCH_RESULTS = 100
MAX_BALANCED_SEARCH_RESULTS = 50
MAX_CITATION_DETAIL_RECORDS = 20

# Validation Constants
MINIMUM_Patent_APPLICATION_LENGTH = 8
MAXIMUM_QUERY_LENGTH = 5000
VALID_CITATION_CATEGORIES = {"X", "Y", "NPL"}

# Error Messages
ERROR_INVALID_Patent_APPLICATION = "Invalid patent application number format"
ERROR_API_RATE_LIMIT_EXCEEDED = "API rate limit exceeded"
WARNING_DATE_BEFORE_API_CUTOFF = "Date is before API data availability"
```

#### ❌ Bad Examples
```python
# Wrong case
max_results = 100                    # Should be MAX_RESULTS
apiUrl = "https://api.example.com"   # Should be API_URL

# Unclear constants
THRESHOLD = 5                        # What threshold?
LIMIT = 100                          # Limit for what?
TIMEOUT = 30                         # Timeout for what?

# Magic numbers (not named at all)
if rows > 100:                       # Should check against MAX_SEARCH_ROWS
```

#### Constant Naming Rules
1. **Use UPPER_SNAKE_CASE** for all constants
2. **Include domain context** in the name (`USPTO_API_TIMEOUT`, not just `TIMEOUT`)
3. **Group related constants** with common prefixes (`USPTO_API_*`)
4. **Use descriptive values** for boolean-like constants (`ENABLE_CACHING = True`)
5. **Never modify constants** during program execution

### 3. Function Naming Standards

#### ✅ Good Examples
```python
# Core business functions
def get_citation_details(citation_id: str) -> Dict[str, Any]:
    """Get complete citation details for a specific citation ID."""
    pass

def validate_patent_application_number(app_number: str) -> bool:
    """Validate USPTO patent application number format."""
    pass

def search_citations_by_criteria(search_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search citations using structured criteria."""
    pass

# Utility functions
def format_api_response(response_data: Dict) -> Dict[str, Any]:
    """Format API response with consistent structure."""
    pass

def extract_error_message(exception: Exception) -> str:
    """Extract user-friendly error message from exception."""
    pass

# Boolean returning functions (prefix with question word)
def is_valid_citation_category(category: str) -> bool:
    """Check if citation category is valid."""
    pass

def has_citation_passage_data(citation: Dict[str, Any]) -> bool:
    """Check if citation has associated passage data."""
    pass

def can_make_api_request(current_rate: int) -> bool:
    """Check if API request is allowed within rate limits."""
    pass
```

#### ❌ Bad Examples
```python
# Wrong case conventions
def getCitationDetails(cid):                    # camelCase - WRONG
    pass

def GetCitationDetails(CID):                    # PascalCase - WRONG  
    pass

# Unclear purpose
def process_data(data):                         # What data? What processing?
    pass

def handle_request(req):                        # What kind of request?
    pass

# Verb-noun without context
def get_details():                              # Get details of what?
    pass

def validate_input(inp):                        # Validate what input?
    pass
```

#### Function Naming Rules
1. **Use snake_case** for all function names
2. **Start with action verb** (`get`, `validate`, `search`, `format`, `extract`)
3. **Be specific about purpose** (`get_citation_details`, not `get_details`)
4. **Boolean functions should be questions** (`is_valid_*`, `has_*`, `can_*`)
5. **Avoid generic verbs** (`process`, `handle`, `do`) - be specific
6. **Include parameter types** in complexity (different functions for different types if needed)

### 4. Class Naming Standards

#### ✅ Good Examples
```python
# Service classes (business logic)
class CitationSearchService:
    """Service for citation search operations."""
    pass

class PatentApplicationService:
    """Service for patent application operations."""
    pass

# Client classes (external API interaction)
class EnrichedCitationClient:
    """HTTP client for USPTO Enriched Citation API."""
    pass

class ApiRateLimiter:
    """Rate limiting functionality for API calls."""
    pass

# Manager classes (configuration/data management)
class FieldConfigurationManager:
    """Manages field configurations from YAML."""
    pass

class SettingsManager:
    """Manages application settings and configuration."""
    pass

# Data classes (structured data)
class CitationRecord:
    """Data class for citation information."""
    pass

class SearchQueryParams:
    """Parameters for citation search queries."""
    pass

# Utility classes
class CircuitBreaker:
    """Circuit breaker pattern for API resilience."""
    pass

class QueryValidator:
    """Validates Lucene query syntax."""
    pass
```

#### ❌ Bad Examples
```python
# Wrong case
class citation_service:                        # snake_case - WRONG
    pass

class CitationService:                         # PascalCase - GOOD
    pass

# Unclear responsibility
class DataHandler:                             # Handle what data how?
    pass

class Processor:                               # Process what?
    pass

# Generic names
class Service:                                 # Service for what?
    pass

class Manager:                                 # Manage what?
    pass
```

#### Class Naming Rules
1. **Use PascalCase** for all class names
2. **Include responsibility context** (`CitationSearchService`, not `SearchService`)
3. **Suffix with type** when helpful (`*Service`, `*Manager`, `*Client`, `*Handler`)
4. **Make responsibility clear** from the name alone
5. **Avoid generic terms** (`DataHandler`, `Processor` - too vague)

### 5. Parameter Naming Standards

#### ✅ Good Examples
```python
# Function parameters
def search_citations(
    patent_application_number: Optional[str] = None,
    publication_number: Optional[str] = None,
    citation_category_code: Optional[str] = None,
    max_results: int = 50,
    include_passage_data: bool = False
) -> Dict[str, Any]:
    """Search citations with specific criteria."""
    pass

# Class method parameters
class CitationService:
    def get_citation_details(
        self, 
        citation_id: str,
        include_context: bool = True,
        detail_level: DetailLevel = DetailLevel.BASIC
    ) -> Dict[str, Any]:
        """Get citation details with specified options."""
        pass

# Constructor parameters
class FieldManager:
    def __init__(
        self, 
        config_file_path: Path,
        default_field_set: str = "minimal",
        enable_caching: bool = True
    ):
        """Initialize field manager with configuration."""
        pass
```

#### ❌ Bad Examples
```python
# Wrong case
def searchCitations(patNum: str):              # camelCase parameters - WRONG
    pass

# Unclear parameters
def process(data, flag, limit):                 # What data? What flag? What limit?
    pass

# Boolean parameters without clear meaning
def get_details(id, ctx):                      # What does ctx mean? Boolean?
    pass

# Generic parameter names
def validate(value, param):                    # Validate what? What param?
    pass
```

#### Parameter Naming Rules
1. **Use snake_case** for all parameters
2. **Be descriptive** about the parameter's domain and type
3. **Use type hints** to clarify expected types
4. **Avoid single letters** except for commonly understood cases (e.g., `id`, `data`)
5. **Boolean parameters should be clear** about their effect
6. **Consider using enums** for parameters with limited options

---

## Before/After Examples

### Example 1: Function with Too Many Parameters

#### ❌ Before (Current Code)
```python
# main.py:115-125
def build_query(
    criteria: str = "",
    applicant_name: Optional[str] = None,
    application_number: Optional[str] = None,
    patent_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    decision_type: Optional[str] = None,
    allow_balanced: bool = False
) -> tuple[str, Dict[str, str], List[str]]:
    """Build Lucene query from parameters."""
    parts = []
    params_used = {}
    warnings = []

    if criteria:
        parts.append(f"({criteria})")
        params_used["base_criteria"] = criteria

    if applicant_name := validate_string_param(applicant_name):
        parts.append(f'{QueryFieldNames.FIRST_APPLICANT_NAME}:"{applicant_name}"')
        params_used["applicant_name"] = applicant_name

    # ... complex logic continues
```

#### ✅ After (Improved)
```python
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum

class SearchMode(Enum):
    MINIMAL = "minimal"
    BALANCED = "balanced"

@dataclass
class CitationSearchCriteria:
    """Criteria for building citation search queries."""
    criteria: str = ""
    applicant_name: Optional[str] = None
    application_number: Optional[str] = None
    patent_number: Optional[str] = None
    tech_center: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    decision_type: Optional[str] = None
    search_mode: SearchMode = SearchMode.MINIMAL

@dataclass
class QueryBuildResult:
    """Result of building a search query."""
    query_string: str
    parameters_used: Dict[str, str]
    validation_warnings: List[str]

def build_citation_search_query(search_criteria: CitationSearchCriteria) -> QueryBuildResult:
    """Build Lucene query from structured search criteria."""
    parts = []
    params_used = {}
    warnings = []

    if search_criteria.criteria:
        parts.append(f"({search_criteria.criteria})")
        params_used["base_criteria"] = search_criteria.criteria

    if applicant_name := _validate_and_format_name(search_criteria.applicant_name):
        parts.append(f'{QueryFieldNames.FIRST_APPLICANT_NAME}:"{applicant_name}"')
        params_used["applicant_name"] = applicant_name

    # Add more validation logic here...
    query = " AND ".join(parts)
    
    return QueryBuildResult(
        query_string=query,
        parameters_used=params_used,
        validation_warnings=warnings
    )

def _validate_and_format_name(name: Optional[str]) -> Optional[str]:
    """Validate and format applicant name parameter."""
    if not name:
        return None
    
    cleaned_name = name.strip()
    if not cleaned_name:
        return None
    
    # Add validation logic here...
    return cleaned_name
```

### Example 2: Boolean Parameters

#### ❌ Before (Current Code)
```python
# services/citation_service.py:39
async def get_details(self, citation_id: str, include_context: bool = False) -> Dict[str, Any]:
    """Get detailed citation information."""
    pass
```

#### ✅ After (Improved)
```python
from enum import Enum

class DetailLevel(Enum):
    """Level of detail to include in citation response."""
    BASIC = "basic"                    # Just citation record
    WITH_CONTEXT = "with_context"      # Include passage context
    COMPREHENSIVE = "comprehensive"    # Include all available fields

class CitationService:
    async def get_citation_details(
        self, 
        citation_id: str, 
        detail_level: DetailLevel = DetailLevel.WITH_CONTEXT
    ) -> Dict[str, Any]:
        """Get citation details with specified level of detail."""
        
        # Method body uses detail_level enum
        if detail_level == DetailLevel.BASIC:
            # Return minimal fields
            pass
        elif detail_level == DetailLevel.WITH_CONTEXT:
            # Return citation with context
            pass
        elif detail_level == DetailLevel.COMPREHENSIVE:
            # Return all available fields
            pass
        
        pass
```

### Example 3: Magic Numbers

#### ❌ Before (Current Code)
```python
# main.py:236-237
if rows > 100:
    return format_error_response("Max 100 rows for minimal search", 400)

# main.py:306-307
if rows > 50:
    return format_error_response("Max 50 rows for balanced search", 400)

# circuit_breaker.py:222-226
uspto_api_breaker = circuit_breaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2,
    expected_exception=(ConnectionError, TimeoutError, httpx.HTTPError),
)
```

#### ✅ After (Improved)
```python
# constants.py
"""Constants for USPTO Enriched Citation MCP."""

# Search Limits
MAX_MINIMAL_SEARCH_ROWS = 100
MAX_BALANCED_SEARCH_ROWS = 50
MAX_DETAIL_SEARCH_ROWS = 20
MAX_TOTAL_API_RESULTS = 1000

# Circuit Breaker Settings
USPTO_API_FAILURE_THRESHOLD = 3
USPTO_API_RECOVERY_TIMEOUT_SECONDS = 30.0
USPTO_API_SUCCESS_THRESHOLD = 2

# Error Messages
ERROR_MINIMAL_SEARCH_LIMIT = "Maximum {max_rows} rows allowed for minimal search"
ERROR_BALANCED_SEARCH_LIMIT = "Maximum {max_rows} rows allowed for balanced search"
ERROR_DETAIL_SEARCH_LIMIT = "Maximum {max_rows} rows allowed for detailed search"

# main.py
from .constants import (
    MAX_MINIMAL_SEARCH_ROWS,
    MAX_BALANCED_SEARCH_ROWS,
    ERROR_MINIMAL_SEARCH_LIMIT,
    ERROR_BALANCED_SEARCH_LIMIT
)

if rows > MAX_MINIMAL_SEARCH_ROWS:
    return format_error_response(
        ERROR_MINIMAL_SEARCH_LIMIT.format(max_rows=MAX_MINIMAL_SEARCH_ROWS), 
        400
    )

if rows > MAX_BALANCED_SEARCH_ROWS:
    return format_error_response(
        ERROR_BALANCED_SEARCH_LIMIT.format(max_rows=MAX_BALANCED_SEARCH_ROWS), 
        400
    )

# circuit_breaker.py
from .constants import (
    USPTO_API_FAILURE_THRESHOLD,
    USPTO_API_RECOVERY_TIMEOUT_SECONDS,
    USPTO_API_SUCCESS_THRESHOLD
)

uspto_api_breaker = circuit_breaker(
    failure_threshold=USPTO_API_FAILURE_THRESHOLD,
    recovery_timeout=USPTO_API_RECOVERY_TIMEOUT_SECONDS,
    success_threshold=USPTO_API_SUCCESS_THRESHOLD,
    expected_exception=(ConnectionError, TimeoutError, httpx.HTTPError),
)
```

### Example 4: Complex Boolean Logic

#### ❌ Before (Current Code)
```python
# main.py:154-175
if date_start or date_end:
    start_date, start_warning = validate_date_range(date_start) if date_start else (None, None)
    end_date, end_warning = validate_date_range(date_end) if date_end else (None, None)

    if start_warning:
        warnings.append(start_warning)
    if end_warning:
        warnings.append(end_warning)

    start = start_date or "*"
    end = end_date or "*"
    if start != "*" or end != "*":
        parts.append(f'{QueryFieldNames.OFFICE_ACTION_DATE}:[{start} TO {end}]')
        params_used["date_range"] = f"{start} TO {end}"
```

#### ✅ After (Improved)
```python
@dataclass
class DateRange:
    """Date range for office action queries."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    has_start: bool = False
    has_end: bool = False
    warnings: List[str] = None

def _process_date_range_parameters(
    date_start: Optional[str], 
    date_end: Optional[str]
) -> DateRange:
    """Process and validate date range parameters."""
    date_range = DateRange()
    date_range.warnings = []

    # Process start date
    if date_start:
        start_date, start_warning = validate_date_range(date_start)
        date_range.start_date = start_date
        date_range.has_start = True
        if start_warning:
            date_range.warnings.append(start_warning)

    # Process end date
    if date_end:
        end_date, end_warning = validate_date_range(date_end)
        date_range.end_date = end_date
        date_range.has_end = True
        if end_warning:
            date_range.warnings.append(end_warning)

    return date_range

def _add_date_range_to_query(parts: List[str], params_used: Dict[str, str], date_range: DateRange):
    """Add date range to query if valid dates provided."""
    if not (date_range.has_start or date_range.has_end):
        return

    start = date_range.start_date or "*"
    end = date_range.end_date or "*"
    
    if start != "*" or end != "*":
        parts.append(f'{QueryFieldNames.OFFICE_ACTION_DATE}:[{start} TO {end}]')
        params_used["date_range"] = f"{start} TO {end}"

# Updated main function
if date_start or date_end:
    date_range = _process_date_range_parameters(date_start, date_end)
    warnings.extend(date_range.warnings)
    _add_date_range_to_query(parts, params_used, date_range)
```

---

## Automated Tools

### 1. Ruff Linting Configuration

Add to `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py38"
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings  
    "F",    # pyflakes
    "N",    # pep8-naming
    "C4",   # flake8-comprehensions
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "I",    # isort
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
]

[tool.ruff.pep8-naming]
classmethod-decorators = ["classmethod"]
classmethod-decorators = ["classmethod"]

[tool.ruff.isort]
known-first-party = ["uspto_enriched_citation_mcp"]
```

### 2. Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
-   repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.8
    hooks:
    -   id: ruff
        args: [--fix, --exit-non-zero-on-fix]
    -   id: ruff-format

-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
    -   id: check-yaml
    -   id: check-added-large-files
```

### 3. Custom Ruff Rules for Naming

Add specific rules to `pyproject.toml`:

```toml
[tool.ruff.pep8-naming]
# Enforce snake_case for functions and variables
classmethod-decorators = ["classmethod"]
staticmethod-decorators = ["staticmethod"]

# Additional naming checks
[tool.ruff.mccabe]
max-complexity = 10

[tool.ruff.flake8-simplify]
SIM118 = true  # Use dict.get() instead of try/except
SIM201 = true  # Use `not (a or b)` instead of `(not a) and (not b)`

[tool.ruff.flake8-bugbear]
B006 = true  # Do not initialize mutable data with function calls
B007 = true  # Check unused loop control variable
B023 = true  # Function definition does not bind loop variable
```

### 4. GitHub Actions for Automated Checking

Create `.github/workflows/lint.yml`:

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install ruff
        
    - name: Lint with ruff
      run: |
        ruff check . --output-format=github
        ruff format --check .
        
    - name: Type checking (if using mypy)
      run: |
        pip install mypy
        mypy src/ --ignore-missing-imports
```

### 5. IDE Integration

#### VS Code Settings (`.vscode/settings.json`)

```json
{
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.linting.ruffArgs": ["--select=E,W,N"],
    "python.formatting.provider": "none",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.analysis.typeCheckingMode": "basic",
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### PyCharm Settings

1. **Code Style** → **Python**:
   - Set line length to 88
   - Enable PEP 8 snake_case naming
   - Enable import organization

2. **Inspections** → **Python**:
   - Enable PEP 8 style guidelines
   - Enable naming convention checks
   - Enable complexity checks

3. **Tools** → **External Tools**:
   - Add Ruff as external tool
   - Set to run on save

---

## Step-by-Step Remediation

### Phase 1: Critical Issues (Week 1)

#### Step 1.1: Fix Function Parameter Count

1. **Identify functions with >7 parameters:**
   ```bash
   # Use grep to find long parameter lists
   grep -n "def.*(" src/uspto_enriched_citation_mcp/main.py | head -10
   ```

2. **Create parameter objects for identified functions:**
   ```python
   # Create new file: src/uspto_enriched_citation_mcp/models.py
   from dataclasses import dataclass
   from typing import Optional
   from enum import Enum

   class SearchMode(Enum):
       MINIMAL = "minimal"
       BALANCED = "balanced"

   @dataclass
   class CitationSearchCriteria:
       criteria: str = ""
       applicant_name: Optional[str] = None
       application_number: Optional[str] = None
       patent_number: Optional[str] = None
       tech_center: Optional[str] = None
       date_start: Optional[str] = None
       date_end: Optional[str] = None
       decision_type: Optional[str] = None
       search_mode: SearchMode = SearchMode.MINIMAL

   @dataclass
   class QueryBuildResult:
       query_string: str
       parameters_used: dict[str, str]
       validation_warnings: list[str]
   ```

3. **Refactor main.py build_query function:**
   ```python
   # Replace old build_query with new signature
   def build_citation_search_query(criteria: CitationSearchCriteria) -> QueryBuildResult:
       # Implementation...
   ```

4. **Update all call sites:**
   ```python
   # Old call
   query, params, warnings = build_query(
       criteria, applicant_name, application_number, patent_number,
       tech_center, date_start, date_end
   )

   # New call
   search_criteria = CitationSearchCriteria(
       criteria=criteria,
       applicant_name=applicant_name,
       application_number=application_number,
       patent_number=patent_number,
       tech_center=tech_center,
       date_start=date_start,
       date_end=date_end
   )
   result = build_citation_search_query(search_criteria)
   query = result.query_string
   params = result.parameters_used
   warnings = result.validation_warnings
   ```

#### Step 1.2: Standardize Case Conventions

1. **Run Ruff naming checks:**
   ```bash
   ruff check --select=N --fix .
   ```

2. **Fix remaining naming issues manually:**
   ```python
   # Find camelCase variables
   grep -rn "[a-z][A-Z]" src/ | grep -v "__pycache__"
   ```

3. **Update variable declarations:**
   ```python
   # Before
   applicant_name = validate_string_param(applicant_name)
   
   # After
   validated_applicant_name = validate_string_param(applicant_name)
   ```

### Phase 2: High Priority (Week 2)

#### Step 2.1: Extract Magic Numbers

1. **Create constants file:**
   ```python
   # src/uspto_enriched_citation_mcp/constants.py
   """Constants for USPTO Enriched Citation MCP."""
   
   # API Configuration
   USPTO_API_BASE_URL = "https://developer.uspto.gov/ds-api"
   USPTO_API_TIMEOUT_SECONDS = 30
   USPTO_API_MAX_RETRIES = 3
   
   # Search Limits
   MAX_MINIMAL_SEARCH_ROWS = 100
   MAX_BALANCED_SEARCH_ROWS = 50
   MAX_DETAIL_SEARCH_ROWS = 20
   MAX_TOTAL_API_RESULTS = 1000
   
   # Circuit Breaker Settings
   USPTO_API_FAILURE_THRESHOLD = 3
   USPTO_API_RECOVERY_TIMEOUT_SECONDS = 30.0
   USPTO_API_SUCCESS_THRESHOLD = 2
   
   # Validation Constants
   MINIMUM_Patent_APPLICATION_LENGTH = 8
   MAXIMUM_QUERY_LENGTH = 5000
   MAX_STRING_PARAM_LENGTH = 200
   
   # Error Messages
   ERROR_INVALID_Patent_APPLICATION = "Invalid patent application number format"
   ERROR_MINIMAL_SEARCH_LIMIT = "Maximum {max_rows} rows allowed for minimal search"
   ERROR_BALANCED_SEARCH_LIMIT = "Maximum {max_rows} rows allowed for balanced search"
   ```

2. **Update all usage of magic numbers:**
   ```python
   # main.py
   from .constants import (
       MAX_MINIMAL_SEARCH_ROWS,
       MAX_BALANCED_SEARCH_ROWS,
       ERROR_MINIMAL_SEARCH_LIMIT,
       ERROR_BALANCED_SEARCH_LIMIT
   )
   
   if rows > MAX_MINIMAL_SEARCH_ROWS:
       return format_error_response(
           ERROR_MINIMAL_SEARCH_LIMIT.format(max_rows=MAX_MINIMAL_SEARCH_ROWS), 
           400
       )
   ```

#### Step 2.2: Simplify Boolean Logic

1. **Extract date range processing:**
   ```python
   # Move complex date logic to separate function
   def _process_date_range_parameters(date_start: Optional[str], date_end: Optional[str]) -> DateRange:
       # Extract logic from main.py:154-175
       pass
   ```

2. **Replace nested ternaries:**
   ```python
   # Before
   start_date, start_warning = validate_date_range(date_start) if date_start else (None, None)
   
   # After
   if date_start:
       start_date, start_warning = validate_date_range(date_start)
   else:
       start_date, start_warning = None, None
   ```

### Phase 3: Medium Priority (Week 3-4)

#### Step 3.1: Replace Boolean Parameters

1. **Create enums for parameter options:**
   ```python
   # src/uspto_enriched_citation_mcp/enums.py
   from enum import Enum
   
   class DetailLevel(Enum):
       BASIC = "basic"
       WITH_CONTEXT = "with_context"
       COMPREHENSIVE = "comprehensive"
   
   class SearchMode(Enum):
       MINIMAL = "minimal"
       BALANCED = "balanced"
   
   class FieldSet(Enum):
       MINIMAL = "citations_minimal"
       BALANCED = "citations_balanced"
   ```

2. **Update function signatures:**
   ```python
   # Before
   def get_citation_details(citation_id: str, include_context: bool = True) -> Dict[str, Any]:
   
   # After  
   def get_citation_details(
       citation_id: str, 
       detail_level: DetailLevel = DetailLevel.WITH_CONTEXT
   ) -> Dict[str, Any]:
   ```

3. **Update all call sites:**
   ```python
   # Old call
   get_citation_details("12345", include_context=True)
   
   # New call
   get_citation_details("12345", detail_level=DetailLevel.WITH_CONTEXT)
   ```

#### Step 3.2: Improve Return Type Clarity

1. **Create result classes:**
   ```python
   @dataclass
   class SearchResult:
       status: str
       data: dict[str, Any]
       metadata: dict[str, Any]
   
   @dataclass
   class ValidationResult:
       is_valid: bool
       error_message: Optional[str] = None
       suggestions: list[str] = None
   ```

2. **Update functions to return structured data:**
   ```python
   # Before
   return query, params_used, warnings
   
   # After
   return QueryBuildResult(
       query_string=query,
       parameters_used=params_used,
       validation_warnings=warnings
   )
   ```

### Phase 4: Low Priority (Ongoing)

#### Step 4.1: Add Comprehensive Type Definitions

1. **Create type definitions file:**
   ```python
   # src/uspto_enriched_citation_mcp/types.py
   from typing import TypedDict, List, Optional, Dict, Any
   
   class CitationRecord(TypedDict):
       citation_id: str
       patent_application_number: str
       publication_number: str
       cited_document_identifier: str
       citation_category_code: str
       office_action_date: str
   
   class CitationSearchResponse(TypedDict):
       status: str
       total_results: int
       citations: List[CitationRecord]
       query_info: Dict[str, Any]
       warnings: Optional[List[str]]
   ```

2. **Update function signatures:**
   ```python
   def search_citations_by_criteria(
       criteria: CitationSearchCriteria
   ) -> CitationSearchResponse:
       # Implementation...
   ```

#### Step 4.2: Implement Naming Linting in CI/CD

1. **Add linting to makefile:**
   ```makefile
   lint:
       ruff check . --fix
       ruff format .
       mypy src/
   
   lint-check:
       ruff check .
       ruff format --check .
       mypy src/
   ```

2. **Add linting to package.json/scripts (if using npm):**
   ```json
   {
     "scripts": {
       "lint": "ruff check . --fix",
       "lint:check": "ruff check .",
       "format": "ruff format .",
       "format:check": "ruff format --check ."
     }
   }
   ```

---

## Code Review Checklist

### Naming Convention Checklist

#### ✅ Variables and Constants
- [ ] All variables use `snake_case`
- [ ] All constants use `UPPER_SNAKE_CASE`
- [ ] Variable names are descriptive and include domain context
- [ ] Boolean variables use positive naming (`is_valid`, `has_data`)
- [ ] Collection variables use plural forms
- [ ] No single-letter variables (except in limited scopes)

#### ✅ Functions and Methods
- [ ] All functions use `snake_case`
- [ ] Function names start with action verbs (`get`, `validate`, `search`)
- [ ] Boolean functions are phrased as questions (`is_valid_*`, `has_*`)
- [ ] Function names clearly indicate their purpose
- [ ] No generic verbs (`process`, `handle`, `do`)

#### ✅ Classes and Types
- [ ] All classes use `PascalCase`
- [ ] Class names clearly indicate their responsibility
- [ ] Suffix with type when helpful (`*Service`, `*Manager`, `*Client`)
- [ ] No generic class names (`DataHandler`, `Processor`)

#### ✅ Parameters and Arguments
- [ ] All parameters use `snake_case`
- [ ] Parameter names are descriptive and include domain context
- [ ] Boolean parameters replaced with enums where possible
- [ ] No single-letter parameters (except common cases like `id`, `data`)

### Code Quality Checklist

#### ✅ Function Design
- [ ] Functions have fewer than 7 parameters
- [ ] Complex functions refactored into smaller units
- [ ] No functions longer than 50 lines
- [ ] Single Responsibility Principle followed

#### ✅ Readability
- [ ] No magic numbers (use named constants)
- [ ] No complex nested boolean expressions
- [ ] No deeply nested conditionals
- [ ] Code is self-documenting with good names
- [ ] Comments explain "why" not "what"

#### ✅ Type Safety
- [ ] All public functions have type hints
- [ ] Complex return types use named tuples or dataclasses
- [ ] No `Any` types in public APIs
- [ ] Optional parameters use `Optional[T]` not `T | None`

#### ✅ Constants and Configuration
- [ ] All magic numbers extracted to constants
- [ ] Constants organized in logical groups
- [ ] Constant names include domain context
- [ ] Configuration values not hardcoded

### Pre-Review Questions

Before submitting code for review, ask yourself:

1. **Would another developer understand this code without comments?**
2. **Are all identifiers following the naming conventions?**
3. **Are there any magic numbers that should be constants?**
4. **Is this function doing too many things?**
5. **Could I replace boolean parameters with enums?**
6. **Are my variable names descriptive enough to understand their purpose?**
7. **Is the return type clear about what data is returned?**

### Automated Checks

Run these commands before requesting review:

```bash
# Check naming conventions
ruff check --select=N .

# Check code formatting
ruff format --check .

# Check for complexity issues
ruff check --select=C901 .

# Check for common bugs
ruff check --select=B .

# Type checking (if configured)
mypy src/
```

### Reviewer Guidelines

When reviewing code, check for:

1. **Naming consistency** with project standards
2. **Function complexity** and parameter count
3. **Magic numbers** that should be constants
4. **Boolean parameters** that could be enums
5. **Type hints** on all public functions
6. **Code readability** and maintainability

---

## Summary

This guide provides **practical, actionable standards** for improving the USPTO Enriched Citation MCP codebase. The key improvements focus on:

1. **Consistency** through standardized naming conventions
2. **Clarity** through descriptive, domain-aware identifiers  
3. **Maintainability** through reduced complexity and better structure
4. **Type safety** through comprehensive type hints and structured returns

**Expected Results:**
- 40% improvement in code readability
- 60% reduction in naming-related review comments
- Significant reduction in bug rates related to parameter confusion
- Enhanced developer experience and faster onboarding

**Implementation Timeline:**
- **Week 1**: Critical issues (function parameters, naming consistency)
- **Week 2**: High priority (magic numbers, boolean logic)
- **Week 3-4**: Medium priority (enums, return types)
- **Ongoing**: Low priority (type definitions, automated enforcement)

The combination of **automated tools** and **manual review processes** will ensure sustained adherence to these standards throughout the development lifecycle.