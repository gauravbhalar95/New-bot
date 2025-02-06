import os
import logging
import yt_dlp
import requests
from config import DOWNLOAD_DIR  # Make sure you have this or set the directory
from utils.sanitize import sanitize_filename

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_twitter_media(url):
    """
    Downloads media (videos or images) from a Twitter URL using yt-dlp.
    """
    try:
        # Set options for yt-dlp to download the best quality video or image
        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "retries": 5,
            "socket_timeout": 10,
            "noplaylist": True,
            "quiet": False,  # Show download progress
            "extract_audio": False,
            "cookiefile": None,  # You can set a cookie file if required for private media
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            },
        }

        # Using yt-dlp to download the content
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = sanitize_filename(info_dict.get("title", "twitter_post"))
            file_ext = info_dict.get("ext", "mp4")
            file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{file_ext}")

            if os.path.exists(file_path):
                logger.info(f"✅ Media downloaded successfully: {file_path}")
                return file_path, os.path.getsize(file_path)
            else:
                logger.error("❌ yt-dlp failed to download media.")
                return None, 0

    except Exception as e:
        logger.error(f"❌ Error downloading media from Twitter: {e}")
        return None, 0

# Test with a Twitter URL
url = "https://x.com/Annupriya997134/status/1885711437986971650?t=0f5kriI0_9dntqWw5dnkGg&s=09"  # Replace with an actual URL
download_twitter_media(url)