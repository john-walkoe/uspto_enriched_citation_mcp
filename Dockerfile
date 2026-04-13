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

RUN uv sync --frozen --no-dev

# HTTP transport — overridden per-service in docker-compose.yml
ENV FASTMCP_TRANSPORT=http
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uv", "run", "uspto-enriched-citation-mcp"]
