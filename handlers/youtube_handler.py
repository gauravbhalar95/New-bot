import os
import yt_dlp
import logging
import requests
import ffmpeg
from pytube import YouTube
from PIL import Image
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR,   # Ensure COOKIES_FILE is defined in config.py
from youtube_cookies import youtube_cookies


# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_video_id(url):
    """ Extracts the video ID using yt-dlp to avoid 'list index out of range' errors. """
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "cookies": youtube_cookies}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get("id", "unknown_video")
    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
        return "unknown_video"

def process_youtube(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': youtube_cookies if os.path.exists(COOKIES_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,  # Logging enabled
        'verbose': True,  # Detailed logs
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # Check if info_dict is None
            if info_dict is None:
                logger.error("yt-dlp returned None. The URL may be invalid.")
                return None, 0

            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get('filesize', 0)

            if not os.path.exists(file_path):
                logger.error(f"Download failed. File not found: {file_path}")
                return None, 0

            logger.info(f"Downloaded video: {file_path} (Size: {file_size} bytes)")
            return file_path, file_size

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0

