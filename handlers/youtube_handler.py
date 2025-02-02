import requests
import os
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, COOKIES_FILE

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_youtube(url):
    """
    Downloads youtube video o

    :param url: The youtube post URL.
    :return: File path and file size if successful, else (None, 0).
    """
    ydl_opts = {
    "format": "best",
    "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
    "retries": 5,
    "socket_timeout": 10,
    "noplaylist": True,
    "cookiefile": COOKIES_FILE,  # Remove quotes, as COOKIES_FILE is a variable
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    },
}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)

           
def download_thumbnail(url, video_path):
    """Download thumbnail and save it in the same directory as the video."""
    if not url:
        return None
    
    thumb_path = os.path.splitext(video_path)[0] + ".jpg"  # Save as .jpg
    try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info_dict)
        file_size = info_dict.get("filesize", 0)
        return file_path, file_size
except Exception as e:
    logger.error(f"Failed to download video: {e}")
    return None, 0  # Return a default value in case of failure