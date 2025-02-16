import yt_dlp
import os
import telebot
import logging
from config import DOWNLOAD_DIR, API_TOKEN, MAX_FILE_SIZE
from utils.thumb_generator import generate_thumbnail

# ✅ Initialize bot in webhook mode (no polling)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_adult(url):
    """
    Downloads an adult video in HD, generates a thumbnail, and returns (file_path, file_size, thumbnail_path, streaming_url).
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'continuedl': True,
        'http_chunk_size': 1048576,
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
                return None, None, None, None

            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            thumbnail_path = generate_thumbnail(file_path)

            streaming_url = info_dict.get('url') or info_dict.get('webpage_url')

            if file_size > MAX_FILE_SIZE:
                logger.info(f"⚠️ File too large ({file_size / (1024 * 1024):.2f} MB). Sending streaming link instead.")
                return None, None, thumbnail_path, streaming_url

            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            return file_path, file_size, thumbnail_path, streaming_url

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None, None

# Example usage
url = "VIDEO_LINK_HERE"
file_path, file_size, thumbnail_path, streaming_url = process_adult(url)

if streaming_url:
    print(f"Streaming URL: {streaming_url}")
elif file_path:
    print(f"Downloaded file: {file_path}, Size: {file_size} bytes")
else:
    print("Download failed.")