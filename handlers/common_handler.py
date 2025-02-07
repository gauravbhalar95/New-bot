import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR
from utils.thumb_generator import generate_thumbnail  # ✅ Import thumbnail function

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Maximum download size limit (100MB)
MAX_DOWNLOAD_SIZE = 1000 * 1024 * 1024  

def process_adult(url, chat_id):
    """Downloads a video, then generates a thumbnail. Returns file if small; otherwise, a streaming link."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # ✅ Download video
            filename = ydl.prepare_filename(info_dict)  # ✅ Get correct filename
            title = info_dict.get('title', 'video')

        if not os.path.exists(filename):
            logger.error(f"⚠️ File not found after download: {filename}")
            return None, None, None, None

        file_size = os.path.getsize(filename)  # ✅ Ensure file size is obtained

        if file_size <= MAX_DOWNLOAD_SIZE:
            # ✅ Generate thumbnail after downloading
            thumbnail_path = generate_thumbnail(filename)
            return filename, file_size, thumbnail_path, None  

        return None, file_size, None, url  # ✅ If too large, return streaming link

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None, None