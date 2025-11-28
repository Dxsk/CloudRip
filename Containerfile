# CloudRip API Container
# OCI-compliant, rootless, security-hardened

# Build stage
FROM docker.io/library/python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/api.txt

# Runtime stage
FROM docker.io/library/python:3.12-alpine AS runtime

# Security labels
LABEL org.opencontainers.image.title="CloudRip API" \
      org.opencontainers.image.description="Find real IP addresses behind Cloudflare" \
      org.opencontainers.image.version="3.0.0" \
      org.opencontainers.image.authors="Dxsk" \
      org.opencontainers.image.source="https://github.com/Dxsk/CloudRip" \
      org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN addgroup -g 1000 -S cloudrip && \
    adduser -u 1000 -S -G cloudrip -h /app cloudrip

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

WORKDIR /app

# Copy application code
COPY --chown=cloudrip:cloudrip cloudrip/ ./cloudrip/
COPY --chown=cloudrip:cloudrip dom.txt ./

# Switch to non-root user
USER cloudrip

# Default environment variables
ENV CLOUDRIP_HOST=0.0.0.0 \
    CLOUDRIP_PORT=8000 \
    CLOUDRIP_WORKERS=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run with minimal privileges
# Using exec form to ensure proper signal handling
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["cloudrip.api:app", "--host", "0.0.0.0", "--port", "8000"]
