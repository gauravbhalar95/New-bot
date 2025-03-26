import os
import re
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def extract_url_and_time(text):
    """Extract URL and Start/End Time using HH:MM:SS format"""
    match = re.match(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", text)
    if match:
        url, start, end = match.groups()
        return url, start, end
    return None, None, None

async def download_youtube_clip(url, start_time, end_time):
    """Download Only the Required Clip Using yt-dlp"""
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
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        return ydl.prepare_filename(info).replace('.webm', '.mp4')

async def process_youtube_request(url):
    """Process YouTube Download for a Specific Clip"""
    url, start, end = await extract_url_and_time(text)
    if not url:
        return "❌ **Invalid Format.** Please send: `<YouTube URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"

    logger.info(f"Downloading Clip: {url}, Start: {start}, End: {end}")

    clip_path = await download_youtube_clip(url, start, end)
    return f"✅ **Clip Ready:** `{clip_path}`" if clip_path else "❌ **Download Failed.**"