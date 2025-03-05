import os
import asyncio
import yt_dlp
import telebot
import logging
import concurrent.futures
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, X_FILE, API_TOKEN

# Initialize logger
logger = setup_logging(logging.DEBUG)

# Initialize Telegram bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

async def download_twitter_media(url):
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
        'http_chunk_size': 2097152,  # 2 MB chunk size for faster downloads
        'noprogress': True,  # Hide progress bar to optimize CPU
        'quiet': True,  # Minimize logs for performance
        'concurrent_fragments': 5,  # Increase concurrent fragment downloads
        'cache-dir': os.path.join(DOWNLOAD_DIR, 'yt_cache'),  # Enable caching
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

async def send_video(chat_id, file_path, thumbnail_path):
    """
    Sends video to Telegram with a thumbnail.
    """
    with open(file_path, "rb") as video:
        thumb = open(thumbnail_path, "rb") if thumbnail_path else None
        await bot.send_video(
            chat_id,
            video,
            thumb=thumb,
            supports_streaming=True,
            timeout=100  # Increased timeout for large files
        )

async def download_and_send(chat_id, url):
    """
    Handles the entire download and send process.
    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        file_path, file_size, thumb = await loop.run_in_executor(pool, download_twitter_media, url)

    if file_path:
        await send_video(chat_id, file_path, thumb)

async def get_streaming_url(url):
    """
    Fetches a streaming URL without downloading the video.
    """
    ydl_opts = {
        'format': 'bv+ba/b',
        'noplaylist': True,
        'cookiefile': X_FILE,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }
    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, False)
            return info_dict.get('url')
    except Exception as e:
        logger.error(f"⚠️ Error fetching streaming URL: {e}")
        return None