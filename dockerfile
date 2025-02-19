# Use official Python image
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . /app

# Install dependencies
RUN pip install -r requirements.txt

# Install Supervisor
RUN apt-get update && apt-get install -y supervisor

# Copy Supervisor config
COPY supervisord.conf /etc/supervisord.conf

# Run Supervisor
CMD ["supervisord", "-c", "/etc/supervisord.conf"]