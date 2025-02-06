import yt_dlp
import os
import telebot
import logging
from config import DOWNLOAD_DIR, COOKIES_FILE
from utils.thumb_generator import generate_thumbnail
from config import API_TOKEN

# ✅ Initialize bot in webhook mode (no polling)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_twitter_media(url, chat_id):
    """Downloads a Twitter/X video in HD, sends thumbnail first, and then returns (file_path, file_size)."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    # Ensure that the video downloaded is in the highest quality available (HD)
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo[height<=1080]+bestaudio/best',  # HD quality, max 1080p video
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    # Add cookies if available
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # Ensure valid response
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None

            # Get actual downloaded file path
            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # Call generate_thumbnail after video is downloaded
            thumbnail_path = generate_thumbnail(file_path)
            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")

            # Send the thumbnail before the video
            if os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as thumb:
                    bot.send_photo(chat_id, thumb, caption="✅ Here's the thumbnail!")

            return file_path, file_size, thumbnail_path

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None