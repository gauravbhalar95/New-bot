import os
import re
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def extract_url_and_time(text):
    """Extracts the YouTube URL and Start/End Time in HH:MM:SS format."""
    match = re.match(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", text)
    if match:
        url, start_time, end_time = match.groups()
        return url, start_time, end_time
    return None, None, None

async def download_youtube_clip(url, start_time, end_time):
    """Downloads only the required clip using yt-dlp."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.mp4")

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'noplaylist': True,
        'download_sections': [f"*{start_time}-{end_time}"],  # Using HH:MM:SS format
    }

    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp4')
            return file_path if os.path.exists(file_path) else None
    except Exception as e:
        logger.error(f"Error downloading YouTube clip: {e}")
        return None

async def process_youtube_request(text):
    """Processes a YouTube download request for a specific clip."""
    url, start_time, end_time = await extract_url_and_time(text)
    if not url:
        return "❌ **Invalid Format.** Please send: `<YouTube URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"

    logger.info(f"Downloading Clip: {url}, Start: {start_time}, End: {end_time}")

    clip_path = await download_youtube_clip(url, start_time, end_time)
    return f"✅ **Clip Ready:** `{clip_path}`" if clip_path else "❌ **Download Failed.**"