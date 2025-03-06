import os
import yt_dlp
import telebot
import logging
from utils.logger import setup_logging
from utils.streaming import get_streaming_url
from config import DOWNLOAD_DIR, X_FILE, API_TOKEN

# Initialize logger
logger = setup_logging(logging.DEBUG)

# Initialize Telegram bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

def download_twitter_media(url):
    """
    Downloads a Twitter/X video in HD and returns (file_path, file_size).
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': X_FILE,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'quiet': True,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # ✅ Remove `await`
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None

            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            logger.info(f"✅ Download completed: {file_path}")

            return file_path, file_size

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None