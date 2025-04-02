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
    """Extracts the URL and Start/End Time in HH:MM:SS format."""
    match = re.match(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", text)
    if match:
        url, start_time, end_time = match.groups()
        return url, time_to_seconds(start_time), time_to_seconds(end_time)
    return None, None, None

async def download_media(url, is_audio=False):
    """Downloads video or audio using yt-dlp."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio' if is_audio else 'bestvideo+bestaudio',
        'outtmpl': output_path,
        'merge_output_format': 'mp4' if not is_audio else 'mp3',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'quiet': True,
        'noplaylist': True,
    }
    
    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)
            if is_audio:
                file_path = file_path.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            else:
                file_path = file_path.replace('.webm', '.mp4').replace('.mkv', '.mp4')
            
            return file_path if os.path.exists(file_path) else None
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

async def trim_media(input_path, start_time, end_time, is_audio=False):
    """Trims the video or audio using ffmpeg."""
    ext = "mp3" if is_audio else "mp4"
    output_path = input_path.replace(f".{ext}", f"_{start_time}_{end_time}.{ext}")

    command = [
        "ffmpeg", "-i", input_path, "-ss", str(start_time), "-to", str(end_time),
        "-c", "copy", "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

    return output_path if os.path.exists(output_path) else None

async def process_trim_request(url, start_time, end_time, is_audio=False):
    """Processes a trim request by downloading and trimming the media."""
    if not url:
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
