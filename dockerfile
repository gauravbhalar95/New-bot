# Use an official Python runtime as a parent image  
FROM python:3.10-slim  

# Set the working directory in the container  
WORKDIR /app  

# Install system dependencies (e.g., ffmpeg) and clean up unnecessary files  
RUN apt-get update && \  
    apt-get install -y --no-install-recommends ffmpeg && \  
    rm -rf /var/lib/apt/lists/*  

# Copy the requirements file and install Python dependencies  
COPY requirements.txt /app/  
RUN pip install --no-cache-dir -r requirements.txt && \  
    pip install --no-cache-dir --upgrade yt-dlp   

# Copy the rest of the application code into the container  
COPY . /app  

# Ensure scripts have execute permissions  
RUN chmod +x /app/update.sh  

# Expose port 8080 for Flask  
EXPOSE 8080

# Set environment variables  
ENV PYTHONUNBUFFERED=1 \  
    FLASK_ENV=production \  
    PORT=8080  

# Run update.sh, then start webhook.py and bot.py  
CMD ["bash", "-c", "/app/update.sh && python webhook.py & python bot.py && tail -f /dev/null"]