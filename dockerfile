# -------------------------------
# Use official Python base image
# -------------------------------
FROM python:3.13-slim

# -------------------------------
# Set working directory
# -------------------------------
WORKDIR /app

# -------------------------------
# Install system dependencies
# -------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        chromium \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Copy & install Python dependencies
# -------------------------------
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp playwright

# -------------------------------
# Install Playwright Chromium
# -------------------------------
RUN playwright install --with-deps chromium

# -------------------------------
# Copy project files
# -------------------------------
COPY . .

# -------------------------------
# Create required directories
# -------------------------------
RUN mkdir -p /app/cookies

# -------------------------------
# Ensure Instagram cookies are present
# (Fixes cookies not deploying issue)
# -------------------------------
COPY utils/instagram_cookies.py /app/utils/instagram_cookies.py

# -------------------------------
# Make shell scripts executable
# -------------------------------
RUN chmod +x /app/update.sh

# -------------------------------
# Environment variables
# -------------------------------
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# -------------------------------
# Expose Flask port
# -------------------------------
EXPOSE 8080

# -------------------------------
# Start Webhook server first, then Telegram bot
# -------------------------------
CMD ["bash", "-c", "python webhook.py & sleep 3 && python bot.py"]