# Use a minimal Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the application files into the container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure yt-dlp is always up-to-date
RUN pip install --no-cache-dir --upgrade yt-dlp

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Ensure bot script is executable
RUN chmod +x bot.py

# Expose the port (if using Flask or any web service)
EXPOSE 8080

# Start the bot
CMD ["python", "-u", "bot.py"]