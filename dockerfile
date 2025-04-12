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

# Install rclone for cloud storage support
RUN curl https://rclone.org/install.sh | bash

# Install mega-cmd for MEGA.nz support
RUN wget https://mega.nz/linux/repo/Debian_11/amd64/megacmd-Debian_11_amd64.deb && \
    apt-get update && \
    apt install -y ./megacmd-Debian_11_amd64.deb && \
    rm megacmd-Debian_11_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories and set permissions
RUN mkdir -p \
        /app/config \
        /app/downloads \
        /app/logs \
        /var/log/supervisor \
        /app/venv && \
    chmod 755 /app/config && \
    chmod 755 /app/downloads && \
    chmod 755 /app/logs

# Setup Python virtual environment
COPY requirements.txt /app/

# Install Python packages
RUN python -m venv /app/venv && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        pyTelegramBotAPI>=4.14.0 \
        aiofiles>=0.8.0 \
        yt-dlp>=2023.3.4 \
        mega.py>=1.0.8 \
        flask>=2.0.1 \
        gunicorn>=20.1.0 \
        python-dotenv>=0.19.0 \
        requests>=2.31.0 \
        telebot>=0.0.5

# Copy application files
COPY . /app/

# Setup supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy and setup health check script
COPY healthcheck.py /app/
RUN chmod +x /app/healthcheck.py

# Create update script
RUN echo '#!/bin/bash\n\
set -e\n\
cd /app\n\
git pull\n\
pip install -r requirements.txt\n\
supervisorctl restart all\n\
echo "Update completed successfully"\n' > /app/update.sh && \
    chmod +x /app/update.sh

# Setup logging
RUN touch /var/log/supervisor/telegram_bot.log && \
    touch /var/log/supervisor/healthcheck.log && \
    chown -R root:root /var/log/supervisor

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Initialize MEGA configuration if needed\n\
if [ ! -f "/app/config/mega_config.json" ]; then\n\
    echo "Initializing MEGA configuration..."\n\
    if [ -z "$MEGA_EMAIL" ] || [ -z "$MEGA_PASSWORD" ]; then\n\
        echo "Error: MEGA_EMAIL and MEGA_PASSWORD must be set"\n\
        exit 1\n\
    fi\n\
    mega-login $MEGA_EMAIL $MEGA_PASSWORD\n\
fi\n\
\n\
# Verify environment variables\n\
for var in TELEGRAM_TOKEN MEGA_EMAIL MEGA_PASSWORD; do\n\
    if [ -z "${!var}" ]; then\n\
        echo "Error: $var is not set"\n\
        exit 1\n\
    fi\n\
done\n\
\n\
# Initialize logs\n\
echo "$(date -u): Container starting up..." >> /app/logs/container.log\n\
\n\
# Start supervisor\n\
echo "Starting supervisor..."\n\
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf\n' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Create a requirements.txt with exact versions
RUN echo "pyTelegramBotAPI==4.14.0\n\
mega.py==1.0.8\n\
aiofiles==24.1.0\n\
yt-dlp==2025.3.31\n\
flask==3.1.0\n\
gunicorn==23.0.0\n\
python-dotenv==1.1.0\n\
requests==2.31.3\n\
telebot==0.0.5\n\
python-telegram-bot==22.0\n" > /app/requirements.txt

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/healthcheck.py || exit 1

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