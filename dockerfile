FROM python:3.13

WORKDIR /app

# Install system dependencies, including ffmpeg and unzip (needed for rclone)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg unzip && \
    rm -rf /var/lib/apt/lists/*

# Install rclone for MediaFire support
RUN curl https://rclone.org/install.sh | bash

# Copy and install Python dependencies
COPY requirements.txt /app/

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade yt-dlp && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Make update.sh executable
RUN chmod +x /app/update.sh

# Expose the port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# Start the bot and webhook server
CMD ["bash", "-c", "/app/update.sh && gunicorn --bind 0.0.0.0:8080 webhook:app & python bot_init.py & python utils.py & python  media_processor.py & python image_processor.py & python handlers.py && tail -f /dev/null"]