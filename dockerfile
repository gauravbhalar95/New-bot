# Use an official lightweight Python image
FROM python:3.12-slim  

# Set the working directory
WORKDIR /app  

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*  

# Copy dependency list and install Python packages
COPY requirements.txt /app/  
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp gunicorn  

# Copy application files
COPY . /app  

# Ensure update.sh has execution permissions
RUN chmod +x /app/update.sh  

# Expose the application port
EXPOSE 9000  

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=9000  

# Start application with better logging
CMD ["/bin/bash", "-c", "echo 'Starting update...' && /app/update.sh && echo 'Update complete, starting services...' && gunicorn -b 0.0.0.0:9000 webhook:app & python bot.py"]