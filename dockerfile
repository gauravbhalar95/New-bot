# Use official Python image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Supervisor
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

# Copy Supervisor config
COPY supervisord.conf /etc/supervisord.conf

# Expose port if needed (optional, only if webhook is used)
EXPOSE 8080

# Copy and set permissions for Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Add the bot processes to Supervisor
RUN echo "[program:bot]\ncommand=python3 bot.py\nautostart=true\nautorestart=true\nstderr_logfile=/dev/stderr\nstdout_logfile=/dev/stdout" >> /etc/supervisor/conf.d/supervisord.conf

RUN echo "[program:webhook]\ncommand=python3 webhook.py\nautostart=true\nautorestart=true\nstderr_logfile=/dev/stderr\nstdout_logfile=/dev/stdout" >> /etc/supervisor/conf.d/supervisord.conf

# Run Supervisor
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]