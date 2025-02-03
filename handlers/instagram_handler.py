import os
import logging
import yt_dlp
import instaloader
from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME
from utils.sanitize import sanitize_filename

# Logger setup
logger = logging.getLogger(__name__)

# Instaloader setup (for private posts & stories)
L = instaloader.Instaloader()
if os.path.exists(COOKIES_FILE):
    L.load_session_from_file("INSTAGRAM_USERNAME", COOKIES_FILE)

def download_instagram(url):
    """
    Downloads Instagram videos, images, or stories using yt-dlp.
    Falls back to Instaloader for private content if necessary.
    """
    ydl_opts = {
        "format": "best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "retries": 5,
        "socket_timeout": 10,
        "noplaylist": True,
        "cookiefile": COOKIES_FILE,  # Use Instagram cookies for authentication
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)

            logger.info(f"Downloaded metadata: {info_dict}")
            logger.info(f"File saved to: {file_path}")

            return file_path, file_size

    except Exception as e:
        logger.error(f"Error downloading with yt-dlp: {e}")

        # Try using Instaloader for private posts or stories
        try:
            shortcode = url.split("/")[-2]
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=DOWNLOAD_DIR)
            return f"{DOWNLOAD_DIR}/{post.shortcode}", 0  # No size info from Instaloader

        except Exception as e:
            logger.error(f"Error downloading with Instaloader: {e}")
            return None, 0

def download_instagram_story(username):
    """
    Downloads Instagram stories for a given username using Instaloader.
    """
    try:
        L.download_stories(userids=[username], filename_target=f"{DOWNLOAD_DIR}/stories/{username}")
        logger.info(f"Stories downloaded for {username}")
        return f"{DOWNLOAD_DIR}/stories/{username}"
    except Exception as e:
        logger.error(f"Error downloading stories: {e}")
        return None

