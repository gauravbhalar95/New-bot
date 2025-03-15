import os
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def process_youtube(url):
    """Download video using yt-dlp asynchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # ✅ Await sanitize_filename() before passing it to yt-dlp
    sanitized_title = await sanitize_filename("%(title)s")

    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitized_title}.%(ext)s',
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

            file_path = ydl.prepare_filename(info_dict)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            return file_path, file_size, None
    except Exception as e:
        logger.error(f"⚠️ Error downloading video: {e}")
        return None, 0, None

async def extract_audio(url):
    """Download and extract audio from a YouTube video asynchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # ✅ Await sanitize_filename() before passing it to yt-dlp
    sanitized_title = await sanitize_filename("%(title)s")

    audio_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitized_title}.%(ext)s',
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

            audio_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            file_size = os.path.getsize(audio_filename) if os.path.exists(audio_filename) else 0
            return audio_filename, file_size
    except Exception as e:
        logger.error(f"⚠️ Error extracting audio: {e}")
        return None, 0