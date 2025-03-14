import os
import asyncio
import yt_dlp
import telebot
import logging
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, X_FILE, API_TOKEN

# Initialize logger
logger = setup_logging(logging.DEBUG)

# Initialize Telegram bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

async def process_adult(url):
    """
    Downloads a Twitter/X video in HD and returns (file_path, file_size, thumbnail_path).
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': X_FILE,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None, None

            file_path = info_dict["requested_downloads"][0]["filepath"]

            # Check if file exists before getting size
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # ✅ Await async function & check for None
            thumbnail_path = await generate_thumbnail(file_path)

            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            else:
                logger.warning("⚠️ Thumbnail generation failed.")

            logger.info(f"✅ Download completed: {file_path}")

            return file_path, file_size, thumbnail_path

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None