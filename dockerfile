FROM python:3.13

WORKDIR /app

# Install system dependencies, including ffmpeg and unzip
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg unzip supervisor && \
    rm -rf /var/lib/apt/lists/*

# Install rclone for MediaFire support
RUN curl https://rclone.org/install.sh | bash

# Install mega-cmd for better MegaNZ support (more reliable than Python lib)
RUN apt-get update && \
    apt-get install -y wget gnupg && \
    wget https://mega.nz/linux/repo/Debian_11/amd64/megacmd-Debian_11_amd64.deb && \
    apt install -y ./megacmd-Debian_11_amd64.deb && \
    rm megacmd-Debian_11_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /app/

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade yt-dlp && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir mega.py flask gunicorn

# Copy source code
COPY . /app/

# Make update.sh executable
RUN chmod +x /app/update.sh

# Setup supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose the port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# Start with supervisor to manage all processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]