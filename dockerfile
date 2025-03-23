# Use a lightweight Python image  
FROM python:3.13-slim  

# Set working directory  
WORKDIR /app  

# Install system dependencies efficiently  
RUN apt-get update && \  
    apt-get install -y --no-install-recommends ffmpeg git unzip && \  
    rm -rf /var/lib/apt/lists/*  

# Install rclone (Fixes the previous issue with missing unzip)  
RUN curl https://rclone.org/install.sh | bash  

# Copy Python dependencies first to leverage Docker cache  
COPY requirements.txt /app/  

# Create and activate a virtual environment  
RUN python -m venv /app/venv  
ENV PATH="/app/venv/bin:$PATH"  

# Install Python dependencies  
RUN pip install --no-cache-dir --upgrade pip && \  
    pip install --no-cache-dir -r requirements.txt  

# Copy the source code  
COPY . /app/  

# Make update.sh executable  
RUN chmod +x /app/update.sh  

# Expose the port  
EXPOSE 8080  

# Set environment variables  
ENV PYTHONUNBUFFERED=1 \  
    QUART_ENV=production \  
    PORT=8080  

# Start the bot and webhook server  
CMD bash -c "/app/update.sh && hypercorn webhook:app --bind 0.0.0.0:8080 & python bot.py"