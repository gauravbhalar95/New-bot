import os
import logging
import yt_dlp
import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
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

# Download Instagram video using yt-dlp
def download_instagram_video(url):
    def download():
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # ✅ yt-dlp options
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
                else:
                    logger.error("❌ Download failed.")
                    return None, 0
        except Exception as e:
            logger.error(f"❌ yt-dlp error: {e}")
            return None, 0

    return executor.submit(download)