# Use Python 3.13 as base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        supervisor \
        curl \
        wget \
        gnupg \
        git \
        procps \
        unzip \
        tzdata \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

# Install MEGA CMD
RUN wget https://mega.nz/linux/repo/Debian_11/amd64/megacmd-Debian_11_amd64.deb && \
    apt-get update && \
    apt install -y ./megacmd-Debian_11_amd64.deb && \
    rm megacmd-Debian_11_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p \
    /app/config \
    /app/downloads \
    /app/logs \
    /var/log/supervisor \
    /app/venv \
    /app/temp && \
    chmod 755 /app/config && \
    chmod 755 /app/downloads && \
    chmod 755 /app/logs && \
    chmod 755 /app/temp

# Copy requirements first
COPY requirements.txt /app/

# Setup Python environment and install packages
RUN python -m venv /app/venv && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        pyTelegramBotAPI==4.14.0 \
        mega.py==1.0.8 \
        flask==3.1.0 \
        gunicorn==23.0.0 \
        python-dotenv==1.1.0 \
        requests==2.32.3 \
        aiohttp==3.11.16 \
        aiofiles==24.1.0 \
        yt-dlp==2025.3.31 \
        telebot==0.0.5

# Copy application files
COPY . /app/

# Create supervisor configuration
RUN echo '[supervisord]\n\
nodaemon=true\n\
logfile=/var/log/supervisor/supervisord.log\n\
pidfile=/var/run/supervisord.pid\n\
user=root\n\
\n\
[program:telegram_bot]\n\
command=/app/venv/bin/python /app/bot.py\n\
directory=/app\n\
user=root\n\
autostart=true\n\
autorestart=true\n\
startretries=5\n\
startsecs=10\n\
stopwaitsecs=10\n\
stdout_logfile=/app/logs/bot.log\n\
stderr_logfile=/app/logs/bot.log\n\
environment=PYTHONUNBUFFERED=1,BOT_TOKEN="%(ENV_BOT_TOKEN)s"\n\
\n\
[program:flask_webhook]\n\
command=/app/venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 4 --threads 2 --timeout 120 app:app\n\
directory=/app\n\
user=root\n\
autostart=true\n\
autorestart=true\n\
startretries=5\n\
startsecs=10\n\
stopwaitsecs=10\n\
stdout_logfile=/app/logs/flask.log\n\
stderr_logfile=/app/logs/flask.log\n\
environment=PYTHONUNBUFFERED=1,BOT_TOKEN="%(ENV_BOT_TOKEN)s"\n\
\n\
[program:mega_sync]\n\
command=/usr/bin/mega-cmd-server\n\
user=root\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/app/logs/mega.log\n\
stderr_logfile=/app/logs/mega.log\n' > /etc/supervisor/conf.d/supervisord.conf

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Function to check if port is available\n\
check_port() {\n\
    for i in {1..30}; do\n\
        if netstat -tln | grep -q ":$1 "; then\n\
            return 0\n\
        fi\n\
        sleep 1\n\
    done\n\
    return 1\n\
}\n\
\n\
# Initialize MEGA configuration\n\
if [ ! -f "/app/config/mega_session.json" ]; then\n\
    echo "Initializing MEGA configuration..."\n\
    if [ -z "$MEGA_EMAIL" ] || [ -z "$MEGA_PASSWORD" ]; then\n\
        echo "Error: MEGA_EMAIL and MEGA_PASSWORD must be set"\n\
        exit 1\n\
    fi\n\
    mega-login "$MEGA_EMAIL" "$MEGA_PASSWORD" || exit 1\n\
fi\n\
\n\
# Verify BOT_TOKEN\n\
if [ -z "$BOT_TOKEN" ]; then\n\
    echo "Error: BOT_TOKEN is not set"\n\
    exit 1\n\
fi\n\
\n\
# Create log files if they don\'t exist\n\
touch /app/logs/bot.log\n\
touch /app/logs/flask.log\n\
touch /app/logs/mega.log\n\
\n\
# Set permissions\n\
chown -R root:root /app/logs\n\
chmod -R 755 /app/logs\n\
\n\
# Start supervisor\n\
echo "Starting supervisor..."\n\
/usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf &\n\
\n\
# Wait for port 8080 to be available\n\
echo "Waiting for Flask webhook to start..."\n\
if ! check_port 8080; then\n\
    echo "Error: Flask webhook failed to start"\n\
    exit 1\n\
fi\n\
\n\
# Keep container running\n\
wait\n' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Create data directory for persistent storage
VOLUME ["/app/config", "/app/downloads", "/app/logs"]

# Labels for container management
LABEL maintainer="gauravbhalar95" \
      version="1.0" \
      description="Telegram Download Bot with MEGA.nz support" \
      created="2025-04-12" \
      org.opencontainers.image.source="https://github.com/gauravbhalar95/New-bot"

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Set working directory
WORKDIR /app