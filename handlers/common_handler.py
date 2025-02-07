import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR
from thumb import generate_thumbnail  # ✅ Import thumbnail function

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Proxy URL
PROXY_URL = "socks5://219.100.37.53:443"

# ✅ Maximum download size limit (100MB)
MAX_DOWNLOAD_SIZE = 1000 * 1024 * 1024  

def process_adult(url, chat_id):
    """Downloads a video, then generates a thumbnail. Returns file if small; otherwise, a streaming link."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'proxy': PROXY_URL,  
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # ✅ Now downloads video first
            video_url = info_dict.get('url')
            file_size = info_dict.get('filesize') or 0  
            title = info_dict.get('title', 'video')

        file_path = os.path.join(DOWNLOAD_DIR, f"{title}.mp4")

        if os.path.exists(file_path) and file_size <= MAX_DOWNLOAD_SIZE:
            # ✅ Generate thumbnail **AFTER** downloading the video
            thumbnail_path = generate_thumbnail(file_path)

            return file_path, file_size, thumbnail_path, None  

        return None, file_size, None, video_url  

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None, None