import os
import logging
import yt_dlp
import instaloader
import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from config import DOWNLOAD_DIR, INSTAGRAM_FILE, INSTAGRAM_PASSWORD, INSTAGRAM_USERNAME
from utils.sanitize import sanitize_filename

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Thread pool for concurrent downloads
executor = ThreadPoolExecutor(max_workers=4)

# Start background memory cleanup
def memory_cleaner():
    while True:
        gc.collect()
        logger.info("🧹 Memory cleaned up")
        threading.Event().wait(60)  # Runs every 60 seconds

threading.Thread(target=memory_cleaner, daemon=True).start()

# Extract shortcode from Instagram URL
def extract_shortcode(url):
    try:
        parts = url.rstrip("/").split("/")
        shortcode = parts[-2] if "?" in parts[-1] else parts[-1]
        logger.info(f"🔍 Extracted shortcode: {shortcode}")
        return shortcode
    except Exception:
        logger.error("❌ Failed to extract shortcode from URL.")
        return None

# Instagram login with Instaloader
def login_instaloader(username, password):
    L = instaloader.Instaloader()
    try:
        L.context.log("🔑 Logging in to Instagram...")
        L.load_session_from_file(username)
        if not L.context.is_logged_in:
            L.login(username, password)
            L.save_session_to_file()
        logger.info(f"✅ Logged in as {username}.")
        return L
    except Exception as e:
        logger.error(f"❌ Login failed: {e}")
        return None

# Download Instagram video (yt-dlp) or images (Instaloader)
def download_instagram(url, username=None, password=None):
    def download():
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # ✅ Try yt-dlp first for videos
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "retries": 5,
            "socket_timeout": 10,
            "noplaylist": True,
            "cookiefile": INSTAGRAM_FILE,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = sanitize_filename(info_dict.get("title", "instagram_post"))
                file_ext = info_dict.get("ext", "mp4")
                file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{file_ext}")

                if os.path.exists(file_path):
                    logger.info(f"✅ Video downloaded successfully: {file_path}")
                    return file_path, os.path.getsize(file_path)
        except Exception as e:
            logger.warning(f"⚠️ yt-dlp failed: {e}. Retrying with Instaloader...")

        # ✅ Try Instaloader for images/private posts
        try:
            shortcode = extract_shortcode(url)
            if not shortcode:
                logger.error("❌ Failed to extract shortcode.")
                return None, 0

            logger.info(f"📥 Attempting to download post with shortcode: {shortcode}")
            post_dir = os.path.join(DOWNLOAD_DIR, shortcode)
            os.makedirs(post_dir, exist_ok=True)

            L = login_instaloader(username, password) if username and password else instaloader.Instaloader(download_videos=False)
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=post_dir)

            post_files = os.listdir(post_dir)
            if post_files:
                post_path = os.path.join(post_dir, post_files[0])
                logger.info(f"✅ Post downloaded successfully: {post_path}")
                return post_path, os.path.getsize(post_path)

            logger.error("❌ No files downloaded. Possible private post or login issue.")
            return None, 0
        except Exception as e:
            logger.error(f"❌ Instaloader error: {e}")
            return None, 0

    return executor.submit(download)