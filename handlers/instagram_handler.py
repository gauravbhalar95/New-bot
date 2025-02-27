import os
import logging
import yt_dlp
import re  # For URL validation
import gc  # For memory cleanup
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging
from handlers.Instagram_image import process_instagram_post

# Initialize logging
logger = setup_logging(logging.DEBUG)

# List of supported domains
SUPPORTED_DOMAINS = ['instagram.com']

# Function to validate URLs
def is_valid_url(url):
    try:
        parsed_url = urlparse(url)
        return parsed_url.scheme in ['http', 'https'] and any(domain in parsed_url.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Function to check if the given Instagram URL is a video
def is_instagram_video(url):
    """Check if the URL corresponds to a Reel, TV, or Video."""
    return any(segment in url for segment in ['/reel/', '/tv/', '/video/'])

# Function to track download progress
def download_progress_hook(status):
    if status['status'] == 'downloading':
        percent = status.get('_percent_str', '0%')
        speed = status.get('_speed_str', 'N/A')
        eta = status.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif status['status'] == 'finished':
        logger.info(f"Download completed: {status['filename']}")

# Function to download Instagram videos using yt-dlp
def process_instagram(url):
    ydl_options = {
        'format': 'bv+ba/b',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'cookiefile': 'cookies.txt',  # Ensure this file is present
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
        'verbose': True,
        'add_header': ['Referer: https://www.instagram.com', 'User-Agent: Mozilla/5.0'],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            file_size = info.get('filesize', 0)
            return file_path, file_size, None
    except Exception as error:
        logger.error(f"Error downloading Instagram video: {error}")
        return None, 0, None

# Function to send the downloaded video to a Telegram user
def send_video_to_user(bot, chat_id, video_path):
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video)
        logger.info(f"Video successfully sent to user {chat_id}")
    except Exception as error:
        logger.error(f"Error sending video to user {chat_id}: {error}")

# Function to clean up downloaded video files
def cleanup_video(video_path):
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
        gc.collect()
        logger.info(f"Deleted {video_path}")
    except Exception as error:
        logger.error(f"Error cleaning up {video_path}: {error}")

# Main handler for Instagram URLs
def handle_instagram_url(url):
    if is_instagram_video(url):
        logger.info("Instagram video detected. Processing with yt-dlp...")
        return process_instagram(url)
    else:
        logger.info("Instagram post/story detected. Processing with Instagram image handler...")
        return process_instagram_post(url)