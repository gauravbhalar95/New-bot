import os
import yt_dlp
import logging
import requests
import ffmpeg
from pytube import YouTube
from PIL import Image
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, COOKIES_FILE  # Ensure COOKIES_FILE is defined in config.py

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_video_id(url):
    """ Extracts the video ID using yt-dlp to avoid 'list index out of range' errors. """
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "cookies": COOKIES_FILE}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get("id", "unknown_video")
    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
        return "unknown_video"

def process_youtube(url):
    """Downloads a YouTube video using yt-dlp with authentication cookies."""
    video_id = get_video_id(url)
    output_path = os.path.join(DOWNLOAD_DIR, sanitize_filename(f"{video_id}.mp4"))

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'cookies': COOKIES_FILE,  # Ensure cookies file exists
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # Log what yt-dlp returns
            logger.info(f"yt-dlp info_dict: {info_dict}")

            file_path = ydl.prepare_filename(info_dict) if info_dict else None
            file_size = info_dict.get("filesize", 0) if info_dict else 0

            if file_path and os.path.exists(file_path):
                logger.info(f"Download successful: {file_path}")
                return file_path, file_size
            else:
                logger.error("yt-dlp did not return a valid file path.")
                return None, 0

    except Exception as e:
        logger.error(f"yt-dlp failed: {e}")
        return None, 0

# Example Usage
if __name__ == "__main__":
    
    # Download video with cookies authentication
    video_path, size = process_youtube(youtube_url)
    if video_path:
        print(f"Downloaded: {video_path} (Size: {size} bytes)")