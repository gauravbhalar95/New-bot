# Use official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/

# Replace pycrypto with pycryptodome during install
RUN sed -i 's/pycrypto/pycryptodome/g' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Copy all project files
COPY . /app

# Make scripts executable
RUN chmod +x /app/update.sh
COPY start.sh .
RUN chmod +x start.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# Expose the port for Flask
EXPOSE 8080

# Start services
CMD bash -c "/app/update.sh && \
    python webhook.py & \
    sleep 5 && \
    python bot.py"