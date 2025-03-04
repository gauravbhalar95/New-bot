FROM python:3.13

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade yt-dlp && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN chmod +x /app/update.sh

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080


CMD ["bash", "-c", "/app/update.sh && gunicorn --bind 0.0.0.0:8080 webhook:app & python bot.py && tail -f /dev/null"]