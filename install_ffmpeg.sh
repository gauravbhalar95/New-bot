#!/bin/bash
echo "Updating package lists and installing ffmpeg..."
apt-get update && apt-get install -y ffmpeg
echo "ffmpeg installed successfully."