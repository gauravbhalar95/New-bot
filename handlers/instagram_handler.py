import os
import logging
import yt_dlp
import re
import gc  # Garbage collection for memory cleanup
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename  # Sanitization utility

def setup_logging(log_level=logging.INFO):
    """Sets up logging configuration."""
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)

    return logger

# Initialize logger with setup_logging
logger = setup_logging()

# Supported domains
SUPPORTED_DOMAINS = ['instagram.com']

def sanitize_filename(url):
    """Check if the given URL is a valid Instagram link."""
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

def download_progress_hook(d):
    """Progress hook for tracking download status."""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

def process_instagram(url):
    """Download Instagram video using yt-dlp."""
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{sanitize_filename("%(title)s")}.%(ext)s'),
        'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
        'verbose': True,  # Enable verbose logging
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0'
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            filesize = info_dict.get('filesize', 0)
            return filename, filesize, None
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {e}")
        return None, 0, str(e)  # Return the error message as a string

def send_video_to_user(bot, chat_id, video_path):
    """Send the downloaded video to a Telegram user."""
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video)
        logger.info(f"Video sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send video to user {chat_id}: {e}")

def cleanup_video(video_path):
    """Clean up the downloaded video file after sending."""
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            gc.collect()
            logger.info(f"Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {video_path}: {e}")