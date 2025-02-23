# Use an official Python runtime as a parent image
FROM python:3.12-slim  

# Set the working directory in the container  
WORKDIR /app  

# Install system dependencies (e.g., ffmpeg) and clean up unnecessary files  
RUN apt-get update && \  
    apt-get install -y --no-install-recommends ffmpeg && \  
    rm -rf /var/lib/apt/lists/*  

# Copy the requirements file and install Python dependencies  
COPY requirements.txt /app/  
RUN pip install --no-cache-dir -r requirements.txt && \  
    pip install --no-cache-dir --upgrade yt-dlp gunicorn  

# Copy the rest of the application code into the container  
COPY . /app  

# Ensure scripts have execute permissions  
RUN chmod +x /app/update.sh  

# Expose port 9000 for Flask  
EXPOSE 9000  

# Set environment variables  
ENV PYTHONUNBUFFERED=1 \  
    FLASK_ENV=production \  
    PORT=9000  

# Run update.sh, then start webhook using Gunicorn  
CMD ["/bin/bash", "-c", "/app/update.sh && gunicorn -b 0.0.0.0:9000 webhook:app & python bot.py"]