# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    gcc \
    python3-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create downloads and logs directories
RUN mkdir -p /app/downloads /app/logs && \
    chmod 777 /app/downloads /app/logs

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies with specific versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir imageio-ffmpeg && \
    pip install --no-cache-dir \
        python-telegram-bot==20.6 \
        python-dotenv==1.0.0 \
        yt-dlp==2023.11.16 \
        ffmpeg-python==0.2.0 \
        instaloader==4.10.1 \
        instagram-private-api==1.6.0.0 \
        aiohttp==3.8.5 \
        aiofiles==23.2.1 \
        asyncio==3.4.3 \
        mega.py==1.0.8 \
        Pillow==10.0.0 \
        loguru==0.7.2 \
        psutil==5.9.5 \
        moviepy==1.0.3 \
        imageio==2.31.1

# Copy the rest of the application
COPY . .

# Set proper permissions
RUN chmod -R 755 /app

# Create a non-root user
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

# Command to run the bot
CMD ["python3", "bot.py"]