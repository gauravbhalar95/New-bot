# Use official Python image as the base image
FROM python:3.12

# Set the working directory inside the container
WORKDIR /app

# Copy the entire project into the container
COPY . /app

# Install required dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure necessary environment variables (if any)
ENV PYTHONUNBUFFERED=1

# Expose a port if needed (e.g., for webhook usage)
EXPOSE 8080

# Run the bot script when the container starts
CMD ["python3", "bot.py"]