# Use a smaller base image
FROM python:3.12-alpine

# Set the working directory
WORKDIR /app

# Install only necessary system dependencies
RUN apk add --no-cache ffmpeg bash

# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

# Copy application files
COPY . /app

# Ensure scripts have execute permissions
RUN chmod +x /app/update.sh

# Expose port 9000
EXPOSE 9000

# Use Supervisor for better process management
CMD ["supervisord", "-c", "/app/supervisord.conf"]