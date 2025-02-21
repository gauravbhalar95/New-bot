# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/requirements.txt

# Install system dependencies (e.g., ffmpeg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install necessary Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Ensure yt-dlp is always up-to-date
RUN pip install --no-cache-dir --upgrade yt-dlp

# Copy the rest of the application code into the container
COPY . /app

# Expose port 8080 for Flask
EXPOSE 8080

# Set environment variables (you can also use a .env file instead)
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Command to run the application
CMD python bot.py & python webhook.py