#!/bin/bash

# Update package list and install FFmpeg
apt-get update && apt-get install -y ffmpeg

# Run the bot
python3 bot.py