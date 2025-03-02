FROM python:3.10

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

EXPOSE 9000

ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=9000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl --fail http://localhost:9000/ || exit 1

RUN adduser -D myuser
USER myuser

CMD ["bash", "-c", "/app/update.sh && gunicorn --bind 0.0.0.0:9000 webhook:app & python bot.py && tail -f /dev/null"]
