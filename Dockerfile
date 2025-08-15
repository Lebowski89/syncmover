
# Use lightweight Python image for multi-arch support
FROM python:3.12-slim

# Create a non-root user for safer execution
RUN useradd -m -u 1000 syncmover

# Set working directory
WORKDIR /app

# Copy application code
COPY syncmover.py .

# Install dependencies
RUN pip install --no-cache-dir requests

# Create log directory and ensure permissions
RUN mkdir -p /logs && chown -R syncmover:syncmover /logs

# Switch to non-root user
USER syncmover

# Entrypoint
ENTRYPOINT ["python", "/app/syncmover.py"]