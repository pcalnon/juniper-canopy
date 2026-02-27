# =============================================================================
# JuniperCanopy — Real-time Monitoring Dashboard
# Multi-stage Dockerfile for production deployment
# =============================================================================
# Build: docker build -f conf/Dockerfile -t juniper-canopy:latest .
# Run:   docker run -p 8050:8050 juniper-canopy:latest
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder — Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Install pinned dependencies from lockfile (best layer caching)
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Install juniper-data-client from git (not yet on PyPI)
RUN pip install --no-cache-dir --no-deps \
    "juniper-data-client @ git+https://github.com/pcalnon/juniper-data-client.git@main"

# Copy project files and install without deps (already installed above)
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

# -----------------------------------------------------------------------------
# Stage 2: Runtime — Minimal production image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="JuniperCanopy"
LABEL org.opencontainers.image.description="Real-time monitoring dashboard for the Juniper ecosystem"
LABEL org.opencontainers.image.authors="Paul Calnon"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/pcalnon/juniper-canopy"

# Create non-root user
RUN groupadd --gid 1000 juniper && \
    useradd --uid 1000 --gid juniper --shell /bin/bash --create-home juniper

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code and configuration
COPY --chown=juniper:juniper src/ ./src/
COPY --chown=juniper:juniper conf/ ./conf/

# Create required directories
RUN mkdir -p logs data images && chown -R juniper:juniper /app

USER juniper

# PYTHONPATH so imports from src/ resolve correctly
ENV PYTHONPATH=/app/src

# Service configuration
ENV CASCOR_ENV=production
ENV CASCOR_DEBUG=false

EXPOSE 8050

# Health check for container orchestration (liveness + readiness)
# start-period=5s: Dash/FastAPI hybrid app with pre-installed deps starts quickly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/v1/health', timeout=5)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050"]
