import os
import yt_dlp
import logging
from config import DOWNLOAD_DIR, YOUTUBE_FILE
from utils.sanitize import sanitize_filename

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_youtube(url):
    """Downloads a YouTube video using yt-dlp and returns its file path and size."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),  # ✅ Ensure valid filename
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # ✅ Ensure the info_dict is valid
            if not info_dict or 'title' not in info_dict:
                logger.error("❌ yt-dlp failed to extract video metadata.")
                return None, 0

            # ✅ Generate a valid filename
            sanitized_title = sanitize_filename(info_dict['title'])
            file_ext = info_dict.get('ext', 'mp4')
            file_path = os.path.join(DOWNLOAD_DIR, f"{sanitized_title}.{file_ext}")

            # ✅ Ensure the file exists
            if not os.path.exists(file_path):
                logger.error(f"❌ Download failed. File not found: {file_path}")
                return None, 0

            file_size = os.path.getsize(file_path)  # ✅ Get actual file size
            logger.info(f"✅ Downloaded video: {file_path} (Size: {file_size} bytes)")
            return file_path, file_size

    except Exception as e:
        logger.error(f"❌ Error downloading video: {e}")
        return None, 0