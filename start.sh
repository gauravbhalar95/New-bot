#!/bin/bash

echo "Updating yt-dlp from GitHub..."
pip install --upgrade git+https://github.com/yt-dlp/yt-dlp.git

# Start your bot
python bot.py