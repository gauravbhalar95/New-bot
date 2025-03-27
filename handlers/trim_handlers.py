import os
import re
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, YOUTUBE_FILE
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def time_to_seconds(time_str):
    """Converts HH:MM:SS to seconds."""
    h, m, s = map(int, time_str.split(":"))
    return h * 3600 + m * 60 + s

async def extract_url_and_time(text):
    """Extracts the YouTube URL and Start/End Time in HH:MM:SS format."""
    match = re.match(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", text)
    if match:
        url, start_time, end_time = match.groups()
        return url, time_to_seconds(start_time), time_to_seconds(end_time)
    return None, None, None

async def download_youtube_clip(url, start_time, end_time):
    """Downloads only the required clip using yt-dlp."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.mp4")

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'quiet': True,
        'noplaylist': True,
        'download_ranges': [{'start_time': start_time, 'end_time': end_time}],
    }

    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp4')
            if os.path.exists(file_path):
                return file_path
            else:
                logger.error(f"File not found: {file_path}")
                return None
    except Exception as e:
        logger.error(f"Error downloading YouTube clip: {e}")
        return None

async def process_youtube_request(url, start_time, end_time):
    """Processes a YouTube download request for a specific clip."""
    if not url:
        return None  # Fix: Return None instead of an invalid error message

    logger.info(f"Downloading Clip: {url}, Start: {start_time}, End: {end_time}")

    clip_path = await download_youtube_clip(url, start_time, end_time)
    return clip_path  # Fix: Return only the file path (or None if it fails)