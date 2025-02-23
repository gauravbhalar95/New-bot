# Use an official Python runtime as a parent image  
FROM python:3.12-slim  

WORKDIR /app  

RUN apt-get update && \  
    apt-get install -y --no-install-recommends ffmpeg && \  
    rm -rf /var/lib/apt/lists/*  

COPY requirements.txt /app/  
RUN pip install --no-cache-dir -r requirements.txt && \  
    pip install --no-cache-dir --upgrade yt-dlp gunicorn  

COPY . /app  

RUN chmod +x /app/update.sh  

EXPOSE 9000  

ENV PYTHONUNBUFFERED=1 \  
    FLASK_ENV=production \  
    PORT=9000  

CMD ["/bin/bash", "-c", "/app/update.sh && gunicorn -b 0.0.0.0:9000 webhook:app & python bot.py"]