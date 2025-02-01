import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from utils.sanitize import sanitize_filename

# Logger
logger = logging.getLogger(__name__)


def process_instagram(url):
    """
    Downloads Instagram videos, images, or stories using yt-dlp.

    :param url: The Instagram post URL.
    :return: File path and file size if successful, else (None, 0).
    """
    ydl_opts = {
    "format": "best",
    "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
    "retries": 5,
    "socket_timeout": 10,
    "noplaylist": True,
    "cookiefile": "COOKIES_FILE",  # Ensure this file is updated
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    },
}
    # Use cookies or login credentials if available
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
    elif INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        ydl_opts["username"] = INSTAGRAM_USERNAME
        ydl_opts["password"] = INSTAGRAM_PASSWORD

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        logger.error(f"Error downloading Instagram media: {e}")
        return None, 0