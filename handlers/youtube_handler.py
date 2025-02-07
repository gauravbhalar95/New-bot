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
    """ Downloads a YouTube video using yt-dlp with authentication cookies. """
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
        'cookies': COOKIES_FILE,  # Use authentication cookies
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        logger.error(f"yt-dlp failed: {e}")
        return None, 0

# Example Usage
if __name__ == "__main__":
    youtube_url = "https://youtube.com/shorts/yWzKm1WkEyI?si=FT7Zd5vLqFKnewJs"

    # Download video with cookies authentication
    video_path, size = process_youtube(youtube_url)
    if video_path:
        print(f"Downloaded: {video_path} (Size: {size} bytes)")