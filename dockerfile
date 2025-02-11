# Use an official lightweight Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code into the container
COPY start.sh /app/start.sh


# Install necessary Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Ensure yt-dlp is always up-to-date
RUN pip install --no-cache-dir --upgrade yt-dlp



# Set environment variables (you can also use a .env file instead)
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production


# Set permissions for execution (if needed)
RUN chmod +x /app/start.sh

# Expose ports if using a web server (optional)
EXPOSE 8080

# Start the bot
CMD ["/bin/bash", "/app/start.sh"]


