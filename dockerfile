# Use official Python image
FROM python:3.9

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

# Run Supervisor
CMD ["supervisord", "-c", "/etc/supervisord.conf"]