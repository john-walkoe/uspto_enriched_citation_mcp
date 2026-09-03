FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependency layer — cached unless pyproject.toml or uv.lock changes
# --no-install-project: install deps only (hatchling needs src/ to build the project itself)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Source and config (now present for the second uv sync that installs the project)
COPY src/ ./src/
COPY field_configs.yaml ./
COPY reference/ ./reference/
COPY scripts/ ./scripts/

RUN uv sync --frozen --no-dev

# HTTP transport — overridden per-service in docker-compose.yml
ENV FASTMCP_TRANSPORT=http
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

# LOG_DIR is explicit because util/logging.py picks /var/log/uspto_mcp only
# when /var/log is writable, which is true for root and false for the service
# user below — without this the log path silently changes to a home
# directory the moment the container stops running as root (S-20).
ENV LOG_DIR=/app/logs
ENV CITATIONS_AUTH_DB_PATH=/app/data/mcp_auth.db

# Run as a non-root service user. Any path-write or RCE bug in this process,
# or in FastMCP/uvicorn/httpx, used to execute as uid 0 — which also owned
# the 0600 secret files, the auth SQLite DB and the log directory.
RUN useradd -r -u 10001 -m -d /home/app app \
    && mkdir -p /app/logs /app/data \
    && chown -R app:app /app /home/app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uv", "run", "uspto-enriched-citation-mcp"]
