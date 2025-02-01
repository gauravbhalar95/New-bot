import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR
from utils.sanitize import sanitize_filename

# Logger
logger = logging.getLogger(__name__)

def process_instagram(url):
    """
    Downloads Instagram videos or images using yt-dlp.

    :param url: The Instagram post URL.
    :return: File path and file size if successful, else (None, 0).
    """
    ydl_opts = {
        "format": "best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "retries": 5,
        "socket_timeout": 10,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        logger.error(f"Error downloading Instagram media: {e}")
        return None, 0
