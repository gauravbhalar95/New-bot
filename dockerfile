# Use an official Python runtime as a base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the project files into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Supervisor
RUN apt-get update && apt-get install -y supervisor

# Copy the Supervisor configuration file
COPY Supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose a port if necessary (optional)
EXPOSE 8080  # Change this if needed

# Start the application with Supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]