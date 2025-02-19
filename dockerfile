# Use an official Python image as base
FROM python:3.9

# Install FFmpeg
RUN apt update && apt install -y ffmpeg

# Set the working directory inside the container
WORKDIR /app

# Copy all project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the bot
CMD ["python", "bot.py"]