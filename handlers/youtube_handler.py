import os
import re
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging
from utils.renamer import rename_file, get_file_extension  # Ensure correct imports

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def extract_url(message):
    """Extract the first valid URL from the message."""
    url_pattern = r"(https?://[^\s]+)"
    match = re.search(url_pattern, message)
    return match.group(0) if match else None

async def process_youtube(message):
    """Download video using yt-dlp asynchronously after extracting the URL."""
    url = await extract_url(message)
    if not url:
        logger.error("❌ No valid URL found in the message.")
        return None, 0, None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Download failed.")
                return None, 0, None 

            original_file_path = ydl.prepare_filename(info_dict)
            ext = await get_file_extension(original_file_path) or ".mp4"
            new_filename = sanitize_filename(f"{info_dict['title']}{ext}")
            renamed_file_path = os.path.join(DOWNLOAD_DIR, new_filename)

            await rename_file(original_file_path, renamed_file_path)  # Corrected
            file_size = os.path.getsize(renamed_file_path) if os.path.exists(renamed_file_path) else 0
            return renamed_file_path, file_size, None
    except Exception as e:
        logger.error(f"⚠️ Error downloading video: {e}")
        return None, 0, None

async def extract_audio(message):
    """Download and extract audio asynchronously after extracting the URL."""
    url = await extract_url(message)
    if not url:
        logger.error("❌ No valid URL found in the message.")
        return None, 0

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    audio_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': logger,
        'verbose': True,
    }
    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Audio download failed.")
                return None, 0

            original_file_path = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            new_filename = sanitize_filename(f"{info_dict['title']}.mp3")
            renamed_file_path = os.path.join(DOWNLOAD_DIR, new_filename)

            await rename_file(original_file_path, renamed_file_path)  # Corrected
            file_size = os.path.getsize(renamed_file_path) if os.path.exists(renamed_file_path) else 0
            return renamed_file_path, file_size
    except Exception as e:
        logger.error(f"⚠️ Error extracting audio: {e}")
        return None, 0