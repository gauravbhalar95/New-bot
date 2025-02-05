import os
import logging
import yt_dlp
import instaloader
from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME
from utils.sanitize import sanitize_filename

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Instaloader setup
L = instaloader.Instaloader()

# Load Instagram session
if os.path.exists(COOKIES_FILE):
    try:
        L.load_session_from_file(INSTAGRAM_USERNAME, COOKIES_FILE)
        logger.info("✅ Instagram session loaded successfully.")
    except Exception as e:
        logger.error(f"❌ Error loading Instagram session: {e}")
        os.remove(COOKIES_FILE)
        logger.info("⚠️ Corrupt session file removed. Please log in again.")

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
    Downloads Instagram videos using yt-dlp or images using Instaloader.
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

            logger.warning("⚠️ yt-dlp did not create the expected file. Retrying with Instaloader...")

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp failed: {e}. Retrying with Instaloader...")

    # ✅ Use Instaloader as fallback (for images & private posts)
    try:
        shortcode = extract_shortcode(url)
        if not shortcode:
            logger.error("❌ Failed to extract shortcode from URL.")
            return None, 0

        logger.info(f"📥 Attempting to download post with shortcode: {shortcode}")

        post = instaloader.Post.from_shortcode(L.context, shortcode)
        user_folder = os.path.join(DOWNLOAD_DIR, post.owner_username)
        os.makedirs(user_folder, exist_ok=True)

        # Download the post
        L.download_post(post, target=user_folder)

        # ✅ Verify downloaded files
        post_files = os.listdir(user_folder)
        if post_files:
            post_path = os.path.join(user_folder, post_files[0])
            logger.info(f"✅ Post downloaded successfully: {post_path}")
            return post_path, os.path.getsize(post_path)

        logger.error("❌ Instaloader did not create any files. Possible reasons: Private post, login issue, or rate limit.")
        return None, 0

    except instaloader.exceptions.PrivateProfileNotFollowedException:
        logger.error("❌ This is a private post, and you are not following the user.")
    except instaloader.exceptions.LoginRequiredException:
        logger.error("❌ Instagram login required. Check your session cookies.")
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"❌ Instaloader error: {e}")

    return None, 0