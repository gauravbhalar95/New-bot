import os
import logging
import yt_dlp
from instalooter import instalooter
from config import DOWNLOAD_DIR, COOKIES_FILE
from utils.sanitize import sanitize_filename

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def extract_shortcode(url):
    """Extracts shortcode from Instagram URL."""
    try:
        parts = url.rstrip("/").split("/")
        shortcode = parts[-2] if "?" in parts[-1] else parts[-1]
        logger.info(f"🔍 Extracted shortcode: {shortcode}")
        return shortcode
    except Exception:
        logger.error("❌ Failed to extract shortcode from URL.")
        return None

def process_instagram(url):
    """
    Downloads Instagram videos using yt-dlp or images using InstaLooter.
    """
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # ✅ Attempt with yt-dlp first (for videos)
        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "retries": 5,
            "socket_timeout": 10,
            "noplaylist": True,
            "cookiefile": COOKIES_FILE,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = sanitize_filename(info_dict.get("title", "instagram_post"))
            file_ext = info_dict.get("ext", "mp4")
            file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{file_ext}")

            if os.path.exists(file_path):
                logger.info(f"✅ Video downloaded successfully: {file_path}")
                return file_path, os.path.getsize(file_path)

            logger.warning("⚠️ yt-dlp did not create the expected file. Retrying with InstaLooter...")

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp failed: {e}. Retrying with InstaLooter...")

    # ✅ Use InstaLooter as fallback (for images & private posts)
    try:
        shortcode = extract_shortcode(url)
        if not shortcode:
            logger.error("❌ Failed to extract shortcode from URL.")
            return None, 0

        logger.info(f"📥 Attempting to download post with shortcode: {shortcode}")

        post_dir = os.path.join(DOWNLOAD_DIR, shortcode)
        os.makedirs(post_dir, exist_ok=True)

        looter = InstaLooter("post", shortcode)
        looter.download(post_dir)

        # ✅ Verify downloaded files
        post_files = os.listdir(post_dir)
        if post_files:
            post_path = os.path.join(post_dir, post_files[0])
            logger.info(f"✅ Post downloaded successfully: {post_path}")
            return post_path, os.path.getsize(post_path)

        logger.error("❌ InstaLooter did not create any files. Possible reasons: Private post, login issue, or rate limit.")
        return None, 0

    except Exception as e:
        logger.error(f"❌ InstaLooter error: {e}")
        return None, 0