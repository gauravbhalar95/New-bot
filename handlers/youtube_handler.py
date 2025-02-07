import os
import yt_dlp
import logging
import re
from config import DOWNLOAD_DIR, SUPPORTED_DOMAINS, YOUTUBE_FILE

logger = logging.getLogger(__name__)

# Utility to sanitize filenames
def sanitize_filename(filename, max_length=250):
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.strip()[:max_length]

# Check if URL is valid
def is_valid_url(url):
    return any(domain in url for domain in SUPPORTED_DOMAINS)

# Download Video from YouTube with Cookies
def process_youtube(url):
    if not is_valid_url(url):
        return None, "Invalid URL"

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 3,
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,  # Use cookies.txt for authentication
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            return file_path, None
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, str(e)