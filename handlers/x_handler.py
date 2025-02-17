import yt_dlp
import os
import telebot
import logging
from config import DOWNLOAD_DIR, X_FILE, API_TOKEN
from utils.thumb_generator import generate_thumbnail

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_twitter_media(url):
    """Downloads a Twitter/X video in HD and returns (file_path, file_size, thumbnail_path)."""

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'cookies_file': X_FILE
        'continuedl': True,
        'http_chunk_size': 1048576,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    if os.path.exists(X_FILE):
        ydl_opts["cookiefile"] = X_FILE

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