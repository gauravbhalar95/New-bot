# Use an official Python runtime as a parent image
FROM python:3.11-slim AS base

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg supervisor && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements file for caching
COPY requirements.txt /app/

# Upgrade pip and install dependencies in a single step
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp google-api-python-client

# Copy the rest of the application
COPY . /app

# Ensure scripts have execute permissions
RUN chmod +x /app/update.sh

# Expose port
EXPOSE 9000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=9000

# Copy Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Run Supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]