import logging
import os
import yt_dlp
import gc
import asyncio
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, INSTAGRAM_FILE  # Ensure INSTAGRAM_FILE is set to your cookies file path
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ['instagram.com']

# Validate URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Check if the URL is a video
def is_instagram_video(url):
    return any(x in url for x in ['/reel/', '/tv/', '/video/'])

# Progress Hook
def download_progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

# Async Instagram Video Download
async def process_instagram(url):
    # Ensure cookies file exists
    if not os.path.exists(INSTAGRAM_FILE) or os.path.getsize(INSTAGRAM_FILE) == 0:
        logger.error("Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    ydl_opts = {
        'format': 'bv+ba/b',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'verbose': True,
        'cookiefile': INSTAGRAM_FILE,  # Use cookies for authentication
    }

    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if info_dict:
                video_path = ydl.prepare_filename(info_dict)
                file_size = info_dict.get('filesize', 0)
                return video_path, file_size, None
            else:
                return None, 0, "Failed to extract info"
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {e}")
        return None, 0, str(e)

# Send Video to User
async def send_video_to_user(bot, chat_id, video_path):
    try:
        with open(video_path, 'rb') as video:
            await bot.send_video(chat_id, video)
        logger.info(f"Video sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send video to user {chat_id}: {e}")

# Cleanup
def cleanup_video(video_path):
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            gc.collect()
            logger.info(f"Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {video_path}: {e}")