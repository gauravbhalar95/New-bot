# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl chromium && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Install Playwright
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# Copy project files
COPY . /app

# 🔥 Ensure Instagram cookies are copied to the container
# (THIS FIXES your "cookies not deploying" issue)
COPY utils/instagram_cookies.py /app/utils/instagram_cookies.py

# Make scripts executable
RUN chmod +x /app/update.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# Expose port for Flask
EXPOSE 8080

# Start Webhook server first, then Bot
CMD bash -c "python webhook.py & sleep 3 && python bot.py"