import os
import subprocess
import yt_dlp
import logging
from utils.sanitize import sanitize_filename  # Sanitization utility
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.renamer import rename_files_in_directory
from utils.logger import setup_logging


def process_youtube(url):
    """Download video using yt-dlp."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                logger.error("No info_dict returned. Download failed.")
                return None, 0, None 
            file_size = info_dict.get('filesize', 0) or 0
            return ydl.prepare_filename(info_dict), file_size, None  # Fixed: Added third value
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0, None

def extract_audio(url):
    """Download and extract audio from a YouTube video using yt-dlp."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    audio_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
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
        return None, 0, None


