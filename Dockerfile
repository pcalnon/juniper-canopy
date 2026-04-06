# =============================================================================
# juniper-canopy — Monitoring Dashboard
# Multi-stage Dockerfile for production deployment
# =============================================================================
# Build: docker build -t juniper-canopy:latest .
# Run:   docker run -p 8050:8050 \
#          -e JUNIPER_DATA_URL=http://localhost:8100 \
#          -e CASCOR_SERVICE_URL=http://localhost:8200 \
#          juniper-canopy:latest
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder — Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Install CPU-only PyTorch first (avoids pulling CUDA which is ~4 GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install pinned dependencies from lockfile (best layer caching)
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Copy project files and install without deps (already installed above)
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY juniper_canopy/ ./juniper_canopy/
RUN pip install --no-cache-dir --no-deps .

# -----------------------------------------------------------------------------
# Stage 2: Runtime — Minimal production image
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="juniper-canopy"
LABEL org.opencontainers.image.description="Real-time monitoring dashboard for juniper-cascor"
LABEL org.opencontainers.image.authors="Paul Calnon"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/pcalnon/juniper-canopy"

# Install curl for lightweight health checks (avoids spawning Python interpreter)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 juniper && \
    useradd --uid 1000 --gid juniper --shell /bin/bash --create-home juniper

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code and configuration
COPY --chown=juniper:juniper src/ ./src/
COPY --chown=juniper:juniper conf/app_config.yaml conf/logging_config.yaml ./conf/
COPY --chown=juniper:juniper conf/layouts/ ./conf/layouts/

# Create required directories
RUN mkdir -p logs && chown -R juniper:juniper /app

USER juniper

# PYTHONPATH so imports from src/ resolve correctly
ENV PYTHONPATH=/app/src

# Service configuration — uses JUNIPER_CANOPY_ prefix for pydantic-settings.
# Nested settings use double-underscore delimiter (SERVER__HOST, SERVER__PORT).
ENV JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
ENV JUNIPER_CANOPY_SERVER__PORT=8050
ENV JUNIPER_CANOPY_DEMO_MODE=false
ENV JUNIPER_CANOPY_LOG_LEVEL=INFO
ENV JUNIPER_DATA_URL=http://juniper-data:8100
ENV CASCOR_SERVICE_URL=http://juniper-cascor:8200
EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail --silent --max-time 5 http://localhost:8050/v1/health || exit 1

CMD ["python", "src/main.py"]
