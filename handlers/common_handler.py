import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, SUPPORTED_DOMAINS
from utils.sanitize import sanitize_filename

# Logger
logger = logging.getLogger(__name__)

def is_supported_url(url):
    """
    Checks if the given URL belongs to a supported domain.

    :param url: The video URL.
    :return: True if supported, False otherwise.
    """
    return any(domain in url for domain in SUPPORTED_DOMAINS)

def download_media(url):
    """
    Downloads media from a given URL using yt-dlp.

    :param url: The media URL.
    :return: File path and file size if successful, else (None, 0).
    """
    ydl_opts = {
        "format": "best[ext=mp4]/best",
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
        logger.error(f"Error downloading media: {e}")
        return None, 0