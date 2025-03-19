FROM python:3.12-slim

WORKDIR /app

# Install dependencies efficiently
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Make update.sh executable
RUN chmod +x /app/update.sh

# Expose the port
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    QUART_ENV=production \
    PORT=8080

# Start the server with proper async support
CMD bash -c "/app/update.sh && hypercorn webhook:app --bind 0.0.0.0:8080 & python bot.py"