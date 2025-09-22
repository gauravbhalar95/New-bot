# Use official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl supervisor && \
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
[program:telegram-bot]
command=python /app/bot.py
autostart=true
autorestart=true
priority=3
environment=PYTHONUNBUFFERED=1,INSTAGRAM_USERNAME=%(ENV_INSTAGRAM_USERNAME)s,INSTAGRAM_PASSWORD=%(ENV_INSTAGRAM_PASSWORD)s,API_TOKEN=%(ENV_API_TOKEN)s,MEGA_EMAIL=%(ENV_MEGA_EMAIL)s,MEGA_PASSWORD=%(ENV_MEGA_PASSWORD)s

# Expose the port for Flask
EXPOSE 8080

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Start Supervisor (which will manage your processes)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]