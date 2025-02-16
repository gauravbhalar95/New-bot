import yt_dlp
import os
import telebot
import logging
from config import DOWNLOAD_DIR, API_TOKEN
from utils.thumb_generator import generate_thumbnail

# ✅ Initialize bot in webhook mode (no polling)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_adult(url):
    """Downloads an adult video in HD, sends thumbnail first, and then returns (file_path, file_size)."""

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    # ✅ yt-dlp options for fast & stable downloads (No Cookies)
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',  # HD quality, max 1080p video
        'noplaylist': True,
        'socket_timeout': 30,  # ⏳ Increased timeout
        'retries': 10,  # 🔁 More retries for stability
        'fragment_retries': 10,  # 🔄 Retry failed fragments
        'continuedl': True,  # ⏯️ Allows resuming downloads
        'http_chunk_size': 1048576,  # 📦 1MB chunks for better speed
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

        try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None, None
            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            thumbnail_path = generate_thumbnail(file_path)
            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            return file_path, file_size, thumbnail_path
    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")
    return None, None, None