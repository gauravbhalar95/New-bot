#!/bin/bash
set -e

echo "Updating yt-dlp from GitHub..."
pip install --upgrade git+https://github.com/yt-dlp/yt-dlp.git

# Start the long-running webhook service.
exec python3 webhook.py
