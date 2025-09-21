# Use official Python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Copy all project files
COPY . /app

# Make scripts executable
RUN chmod +x /app/update.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# Expose the port for Flask
EXPOSE 8080

CMD bash -c "/app/update.sh && \
    python webhook.py & \
    sleep 5 && \
    python bot.py"