# ----------------------
# Stage 1: Builder
# ----------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy requirements and install packages into /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application files
COPY syncmover.py .
COPY docker-entrypoint.sh .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# ----------------------
# Stage 2: Final
# ----------------------
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user
RUN useradd -m -u 1000 syncmover

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# Create logs directory and set ownership
RUN mkdir -p /logs && chown -R syncmover:syncmover /logs /app

# Default environment variables (can be overridden in docker-compose)
ENV LOG_FILE=/logs/syncmover.log
ENV LOG_LEVEL=INFO
ENV DRY_RUN=false

# Switch to non-root user
USER syncmover

# Entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]