# Use an official Python base image
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies needed by yt-dlp and media processing.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

COPY . .

RUN mkdir -p /app/cookies && chmod +x /app/update.sh

ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

EXPOSE 8080

CMD ["python3", "webhook.py"]
