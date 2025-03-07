FROM python:3.10

WORKDIR /app

# ✅ Install FFmpeg and Dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg libavcodec-extra supervisor && \
    rm -rf /var/lib/apt/lists/*

# ✅ Copy and Install Python Packages
COPY requirements.txt /app/
RUN python -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ✅ Copy All Files
COPY . /app/

# ✅ Ensure Scripts are Executable
RUN chmod +x /app/update.sh

# ✅ Expose Port
EXPOSE 8080

# ✅ Set Environment Variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

# ✅ Use Supervisor for Process Management
CMD ["supervisord", "-c", "/app/supervisord.conf"]