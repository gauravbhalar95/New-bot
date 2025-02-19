# Use an official Python image
FROM python:3.10

# Switch to root user for installing packages
USER root

# Install FFmpeg and dependencies
RUN apt-get update && apt-get install -y ffmpeg

# Create a non-root user (for security)
RUN useradd -m appuser

# Switch back to non-root user
USER appuser

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the bot
CMD python3 bot.py & python3 webhook.py && wait