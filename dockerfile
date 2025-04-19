# Use Python 3.9 slim image as base
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

# Create downloads directory
RUN mkdir -p /app/downloads && \
    chmod 777 /app/downloads

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

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