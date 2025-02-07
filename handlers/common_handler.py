import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Define proxy URL (Change this to your actual proxy)
PROXY_URL = "socks5://219.100.37.53:443"

def download_video(url, chat_id):
    """Downloads a video using yt-dlp with a proxy."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',  # Best available quality in MP4
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'proxy': PROXY_URL,  # ✅ Add proxy support
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None

            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            return file_path, file_size

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None