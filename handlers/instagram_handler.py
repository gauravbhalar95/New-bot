import os
import logging
import yt_dlp
import re
from urllib.parse import urlparse
import gc  # Garbage collection for memory cleanup
from config import DOWNLOAD_DIR, INSTAGRAM_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
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
    ydl_opts = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
    'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None,  # Ensure cookie file exists
    'socket_timeout': 10,
    'retries': 5,
    'progress_hooks': [download_progress_hook],
    'logger': logger,
    'verbose': True,
    'extractor_retries': 5
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0), None
except Exception as e:
    logger.error(f"Error downloading Instagram video: {e}")
    return None, 0, None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0), None  # Fixed: Added third value
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {e}")
        return None, 0, None

# Send video to user (bot instance will be passed from main)
def send_video_to_user(bot, chat_id, video_path):
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video)
        logger.info(f"Video sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send video to user {chat_id}: {e}")

# Cleanup after download
def cleanup_video(video_path):
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            gc.collect()
            logger.info(f"Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {video_path}: {e}")