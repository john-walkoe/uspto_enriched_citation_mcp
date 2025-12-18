"""
Application constants for USPTO Enriched Citation MCP.

Replaces magic numbers with named constants for better maintainability.
"""

from datetime import datetime

# === API DATA AVAILABILITY ===
# USPTO Enriched Citation API data coverage dates
API_DATA_START_DATE = datetime(2017, 10, 1)  # October 1, 2017
API_DATA_CUTOFF_DATE_STRING = "2017-10-01"

# Application filing date for context (accounting for 1-2 year filing-to-OA lag)
APPLICATION_FILING_START_DATE = datetime(2015, 1, 1)
APPLICATION_FILING_START_DATE_STRING = "2015-01-01"

# === REQUEST LIMITS ===
# Maximum rows per API request
MAX_ROWS_PER_REQUEST = 1000

# Default pagination sizes
DEFAULT_MINIMAL_SEARCH_ROWS = 50
DEFAULT_BALANCED_SEARCH_ROWS = 20
MAX_MINIMAL_SEARCH_ROWS = 100
MAX_BALANCED_SEARCH_ROWS = 50

# === QUERY VALIDATION ===
# Maximum query length (characters)
MAX_QUERY_LENGTH = 5000

# Maximum wildcards in query (DoS protection)
MAX_WILDCARDS_PER_QUERY = 10

# Maximum nesting depth for parentheses/brackets
MAX_QUERY_NESTING_DEPTH = 20

# Maximum range queries
MAX_RANGE_QUERIES = 10

# === API CONFIGURATION ===
# USPTO API base URL
DEFAULT_BASE_URL = "https://developer.uspto.gov/ds-api"

# === MCP SERVER ===
# Default MCP server port
DEFAULT_MCP_SERVER_PORT = 8081

# === RATE LIMITING ===
# Default rate limit (requests per minute)
DEFAULT_RATE_LIMIT_RPM = 100

# === TIMEOUTS ===
# API request timeouts (seconds)
DEFAULT_API_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 10.0

# === CONNECTION POOLING ===
# HTTP client connection limits
MAX_KEEPALIVE_CONNECTIONS = 5
MAX_TOTAL_CONNECTIONS = 10

# === RETRY CONFIGURATION ===
# Retry defaults
DEFAULT_MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds
DEFAULT_RETRY_MAX_DELAY = 30.0  # seconds
DEFAULT_RETRY_EXPONENTIAL_BASE = 2.0

# === CIRCUIT BREAKER ===
# Circuit breaker thresholds
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30.0  # seconds
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 2

# === LOGGING ===
# Default log level
DEFAULT_LOG_LEVEL = "INFO"

# Default request ID header
DEFAULT_REQUEST_ID_HEADER = "X-Request-ID"

# Log preview lengths (characters)
LOG_QUERY_PREVIEW_LENGTH = 100
LOG_ERROR_MESSAGE_MAX_LENGTH = 200

# === SECURITY ===
# API key validation
MIN_API_KEY_LENGTH = 28
MAX_API_KEY_LENGTH = 40

# Request/Response size limits (bytes)
MAX_RESPONSE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB (DoS protection)
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB (query size limit)
WARNING_RESPONSE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB (log warning threshold)

# === CACHING ===
# Cache configuration
ENABLE_CACHE_DEFAULT = True
FIELDS_CACHE_TTL_SECONDS = 3600  # 1 hour (fields rarely change)
SEARCH_CACHE_SIZE = 100  # Max 100 cached search results (LRU)
FIELDS_CACHE_SIZE = 10  # Max 10 cached field responses

# === FIELD CONFIGURATION ===
# Default field configuration file path
DEFAULT_FIELD_CONFIG_PATH = "field_configs.yaml"

# === FIELD COUNTS ===
# Expected field counts for validation
MINIMAL_FIELD_COUNT = 8
BALANCED_FIELD_COUNT = 18

# === TOKEN EFFICIENCY ===
# Expected context reduction percentages
MINIMAL_CONTEXT_REDUCTION_PERCENT = 90  # 90-95%
BALANCED_CONTEXT_REDUCTION_PERCENT = 80  # 80-85%
ULTRA_MINIMAL_CONTEXT_REDUCTION_PERCENT = 99  # 99%

# === STATUS CODES ===
# Common HTTP status codes (for reference)
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504
