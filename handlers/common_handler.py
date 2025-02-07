import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR
from utils.thumb_generator import generate_thumbnail  # ✅ Import thumbnail function

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Maximum file size limit (100MB)
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  

def process_adult(url, chat_id):
    """Downloads an adult video in HD, generates a thumbnail, and sends it before sending the video."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    # ✅ Optimized yt-dlp options
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4]/best',  # HD quality (max 1080p)
        'noplaylist': True,
        'socket_timeout': 30,  # ⏳ Increased timeout
        'retries': 10,  # 🔁 Increased retries
        'fragment_retries': 10,  # 🔄 Retry failed fragments
        'continuedl': True,  # ⏯️ Allows resuming partial downloads
        'http_chunk_size': 1048576,  # 📦 Download in 1MB chunks
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # ✅ Ensure valid response
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None, None, None

            # ✅ Get actual downloaded file path
            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            if not os.path.exists(file_path):
                logger.error(f"⚠️ File not found: {file_path}")
                return None, None, None, None

            # ✅ Generate thumbnail after downloading
            thumbnail_path = generate_thumbnail(file_path)
            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")

            # ✅ Send thumbnail before video
            if os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as thumb:
                    bot.send_photo(chat_id, thumb, caption="✅ Here's the thumbnail!")

            return file_path, file_size, thumbnail_path

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None, None