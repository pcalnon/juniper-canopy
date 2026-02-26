# Docker configuration for Juniper Canopy
# Build: docker build -t juniper_canopy .
# Run: docker run -p 8050:8050 juniper_canopy
FROM python:3.9-slim

RUN useradd -d /home/juniper -m -s /bin/bash juniper
USER juniper

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV CASCOR_ENV=production
ENV CASCOR_DEBUG=false

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY conf/ ./conf/
COPY utils/ ./utils/

# Create necessary directories
RUN mkdir -p logs data images

# Expose port
EXPOSE 8050

# Health check for container orchestration (liveness + readiness)
# start-period=5s: Dash/FastAPI hybrid app with pre-installed deps starts quickly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8050/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8050"]
