import os
import yt_dlp
import logging
from utils.sanitize import sanitize_filename  # Sanitization utility
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

# Initialize logger
logger = setup_logging(logging.DEBUG)  # Example of setting to debug level.

def ensure_download_dir():
    """Ensure the download directory exists."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_common_ydl_opts():
    """Returns common options for yt-dlp."""
    return {
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }

def process_youtube(url):
    """Download video using yt-dlp."""
    ensure_download_dir()
    
    ydl_opts = {
        **get_common_ydl_opts(),
        'format': 'bv+ba/b',  # Best video + best audio
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                logger.error("No info_dict returned. Download failed.")
                return None, 0, None

            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get('filesize', 0) or 0

            return file_path, file_size, None  # Fixed: Ensured three return values
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0, None

def extract_audio(url):
    """Download and extract audio from a YouTube video using yt-dlp."""
    ensure_download_dir()
    
    audio_opts = {
        **get_common_ydl_opts(),
        'format': 'bestaudio/best',  # Best available audio
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                logger.error("No info_dict returned. Audio download failed.")
                return None, 0

            audio_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            file_size = os.path.getsize(audio_filename) if os.path.exists(audio_filename) else 0

            return audio_filename, file_size
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return None, 0