# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    ffmpeg \
    git \
    curl \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /var/log/supervisor /var/run /app /downloads

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies with specific versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create directories for supervisor
RUN mkdir -p /var/log/supervisor

# Set permissions
RUN chmod -R 755 /app && \
    chmod -R 755 /var/log/supervisor && \
    chmod -R 755 /var/run && \
    mkdir -p /app/downloads && \
    chmod 777 /app/downloads

# Expose necessary ports (if any)
# EXPOSE 8000

# Command to run supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]