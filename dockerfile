# Use official Python image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (only if using a webhook)
EXPOSE 8080

# Start the bot directly (keeping the container alive)
CMD ["python3", "bot.py"]