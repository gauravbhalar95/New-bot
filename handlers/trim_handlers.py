import os
import re
import asyncio
import yt_dlp
import logging
import subprocess
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

async def download_youtube_video(url):
    """Downloads the full YouTube video using yt-dlp."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.%(ext)s")

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'quiet': True,
        'noplaylist': True,
    }

    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp4')  # Ensure MP4 format
            return file_path if os.path.exists(file_path) else None
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        return None

async def trim_video(input_path, start_time, end_time):
    """Trims the video using ffmpeg."""
    output_path = input_path.replace(".mp4", f"_{start_time}_{end_time}.mp4")

    command = [
        "ffmpeg", "-i", input_path, "-ss", str(start_time), "-to", str(end_time),
        "-c", "copy", "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

    return output_path if os.path.exists(output_path) else None

async def process_youtube_request(url, start_time, end_time):
    """Processes a YouTube request by downloading and trimming the video."""
    if not url:
        return None

    logger.info(f"Downloading Video: {url}")
    video_path = await download_youtube_video(url)
    
    if not video_path:
        logger.error("Failed to download video.")
        return None

    logger.info(f"Trimming Video: Start: {start_time}s, End: {end_time}s")
    trimmed_path = await trim_video(video_path, start_time, end_time)

    if trimmed_path:
        return trimmed_path
    else:
        logger.error("Failed to trim video.")
        return None