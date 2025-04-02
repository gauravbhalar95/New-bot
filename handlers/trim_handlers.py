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
    try:
        h, m, s = map(int, time_str.split(":"))
        return h * 3600 + m * 60 + s
    except ValueError:
        return None

def extract_url_and_time(text):
    """Extracts the URL and Start/End Time in HH:MM:SS format."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", text)
    if match:
        url, start_time, end_time = match.groups()
        start_sec, end_sec = time_to_seconds(start_time), time_to_seconds(end_time)
        if start_sec is None or end_sec is None:
            return None, None, None
        return url, start_sec, end_sec
    return None, None, None

async def download_media(url, is_audio=False):
    """Downloads video or audio using yt-dlp."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio' if is_audio else 'bestvideo+bestaudio',
        'outtmpl': output_path,
        'merge_output_format': 'mp4' if not is_audio else 'mp3',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'quiet': False,  # Set to False for debugging
        'noplaylist': True,
    }

    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)
            file_path = file_path.rsplit(".", 1)[0] + (".mp3" if is_audio else ".mp4")  # Ensure correct file extension
            return file_path if os.path.exists(file_path) else None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error downloading media: {e}")
        return None

async def trim_media(input_path, start_time, end_time, is_audio=False):
    """Trims the video or audio using ffmpeg."""
    ext = "mp3" if is_audio else "mp4"
    output_path = input_path.rsplit(".", 1)[0] + f"_{start_time}_{end_time}.{ext}"

    command = [
        "ffmpeg", "-i", input_path, "-ss", str(start_time), "-to", str(end_time),
        "-c", "copy", "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode == 0 and os.path.exists(output_path):
        return output_path
    else:
        logger.error(f"FFmpeg error: {stderr.decode()}")
        return None

async def process_trim_request(text, is_audio=False):
    """Processes a trim request by extracting URL, downloading, and trimming the media."""
    url, start_time, end_time = extract_url_and_time(text)

    if not url or start_time is None or end_time is None:
        logger.error("Invalid input format. Expected: '<url> <start_time> <end_time>'")
        return None

    if start_time >= end_time:
        logger.error("Invalid trim range: Start time must be less than end time.")
        return None

    logger.info(f"Downloading {'Audio' if is_audio else 'Video'}: {url}")
    media_path = await download_media(url, is_audio)

    if not media_path:
        logger.error("Failed to download media.")
        return None

    logger.info(f"Trimming {'Audio' if is_audio else 'Video'}: Start: {start_time}s, End: {end_time}s")
    trimmed_path = await trim_media(media_path, start_time, end_time, is_audio)

    if trimmed_path:
        return trimmed_path
    else:
        logger.error("Failed to trim media.")
        return None