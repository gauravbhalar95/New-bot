# Use stable Python version
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        netcat-traditional \
        git \
        procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
ENV VIRTUAL_ENV=/app/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Copy application code
COPY . .

# Make scripts executable and ensure proper line endings
RUN chmod +x /app/update.sh /app/docker-entrypoint.sh && \
    sed -i 's/\r$//' /app/update.sh && \
    sed -i 's/\r$//' /app/docker-entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Create non-root user for security
RUN groupadd -r botuser && \
    useradd -r -g botuser -s /sbin/nologin -d /app botuser && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Create necessary directories with proper permissions
RUN mkdir -p /app/downloads /app/logs && \
    chmod 755 /app/downloads /app/logs

# Expose the port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use the entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]