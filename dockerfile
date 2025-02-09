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

# Copy the project files into the container
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set environment variables (if needed)
ENV PYTHONUNBUFFERED=1

# Set permissions for execution (if needed)
RUN chmod +x bot.py

# Expose ports if using a web server (optional)
EXPOSE 8080

# Start the bot
CMD python bot.py