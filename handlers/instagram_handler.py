import os
import logging
import yt_dlp
import re
from urllib.parse import urlparse
import gc  # Garbage collection for memory cleanup
from config import DOWNLOAD_DIR, DOWNLOAD_DIR2, DOWNLOAD_DIR3, INSTAGRAM_FILE
from utils.sanitize import is_valid_url  # Sanitization utility

logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = ['instagram.com']

# Validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Sanitize filename
def sanitize_filename(name):
    return re.sub(r'[\/:*?"<>|]', '', name)

# Ensure the download directory exists
def ensure_download_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Progress hook for downloads
def download_progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

# Process Instagram content (images, videos, stories)
def process_instagram(url):
    ensure_download_dir_exists(DOWNLOAD_DIR)  # Ensure the main download directory exists
    if "story" in url:  # If it's a story, use the specific directory for stories
        ensure_download_dir_exists(DOWNLOAD_DIR3)  # Ensure story download directory exists
        download_directory = DOWNLOAD_DIR3
    elif "media" in url:  # If it's an image, use the specific directory for images
        ensure_download_dir_exists(DOWNLOAD_DIR2)  # Ensure image download directory exists
        download_directory = DOWNLOAD_DIR2
    else:  # For other media, use the default download directory
        download_directory = DOWNLOAD_DIR

    ydl_opts = {
        'format': 'best[ext=mp4]/best',  # For videos, change this line if you want images
        'outtmpl': f'{download_directory}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
        'verbose': True,
        'extract_flat': True,  # If you want only the metadata without downloading media
        'noplaylist': True,  # Don't process Instagram posts with multiple media
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0), None  # Fixed: Added third value
    except Exception as e:
        logger.error(f"Error downloading Instagram content: {e}")
        return None, 0, None

# Send media to user (bot instance will be passed from main)
def send_media_to_user(bot, chat_id, media_path, media_type="video"):
    try:
        with open(media_path, 'rb') as media:
            if media_type == "video":
                bot.send_video(chat_id, media)
            elif media_type == "photo":
                bot.send_photo(chat_id, media)
            logger.info(f"{media_type.capitalize()} sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send {media_type} to user {chat_id}: {e}")

# Cleanup after download
def cleanup_media(media_path):
    try:
        if os.path.exists(media_path):
            os.remove(media_path)
            gc.collect()
            logger.info(f"Cleaned up {media_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {media_path}: {e}")