import os
import logging
import yt_dlp
import re
from urllib.parse import urlparse
import gc  # Garbage collection for memory cleanup
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Initialize logger
logger = setup_logging()

# Supported domains
SUPPORTED_DOMAINS = ['instagram.com']

# Validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Progress hook for downloads
def download_progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

def process_instagram(url):
    sanitized_title = sanitize_filename("%(title)s")
    output_path = os.path.join(DOWNLOAD_DIR, f"{sanitized_title}.%(ext)s")

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
        'verbose': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            if info_dict and isinstance(info_dict, dict):
                video_path = ydl.prepare_filename(info_dict)
                file_size = info_dict.get('filesize', 0)
                return video_path, file_size
            else:
                logger.error("Failed to retrieve video info.")
                return None, 0

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

    return None, 0

# Send video to user (bot instance will be passed from main)
def send_video_to_user(bot, chat_id, video_path):
    try:
        if not video_path or not os.path.exists(video_path):
            logger.error(f"File not found: {video_path}")
            return

        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video)
        logger.info(f"Video sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send video to user {chat_id}: {e}")

# Cleanup after download
def cleanup_video(video_path):
    try:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
            gc.collect()
            logger.info(f"Cleaned up {video_path}")
        else:
            logger.warning(f"Cleanup skipped, file not found: {video_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {video_path}: {e}")
