# ✅ Use a minimal Python image for efficiency
FROM python:3.10-slim

# ✅ Set the working directory
WORKDIR /app

# ✅ Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ✅ Copy application files
COPY . .

# ✅ Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Keep yt-dlp updated for latest video support
RUN pip install --no-cache-dir --upgrade yt-dlp

# ✅ Define environment variables
ENV PYTHONUNBUFFERED=1 FLASK_ENV=production PORT=8080

# ✅ Expose Flask's default port
EXPOSE 8080

# ✅ Start both the auto-fix script and bot concurrently
CMD python auto_fix.py & python bot.py