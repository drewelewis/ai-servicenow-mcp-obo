# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source and install the package
COPY pyproject.toml README.md ./
COPY mcp_server_servicenow ./mcp_server_servicenow
RUN pip install --no-cache-dir .

# Bind to all interfaces on the container port (FastMCP reads these)
ENV FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Start the MCP server over SSE (HTTP) transport for remote hosting
CMD ["python", "-m", "mcp_server_servicenow.cli", "--transport", "sse"]
