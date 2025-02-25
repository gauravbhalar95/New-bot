import os
import logging
import yt_dlp
import re  # Regular expressions for validation
import gc  # Garbage collection for memory cleanup
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging
from handlers.Instagram_image import process_instagram_post

# Initialize logger
logger = setup_logging(logging.DEBUG)  # Example of setting to debug level.

# Supported domains
SUPPORTED_DOMAINS = ['instagram.com']

# Validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Detect whether the URL is a reel/video or an image/post
def is_instagram_video(url):
    """ Check if the URL belongs to a Reel or Video """
    return any(x in url for x in ['/reel/', '/tv/', '/video/'])

# Progress hook for downloads
def download_progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

# Process Instagram Video Download
def process_instagram(url):
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'cookiefile': INSTAGRAM_FILE,  # Ensure this points to the correct Instagram cookies file
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
        'verbose': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get('filesize', 0)
            return video_path, file_size, None  # Return video path and size
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

# Main Instagram Handler
def handle_instagram_url(url):
    if is_instagram_video(url):
        # If it's a Reel or Video, process with yt-dlp
        logger.info("Detected Instagram Video/Reel. Processing with yt-dlp...")
        return process_instagram(url)
    else:
        # If it's a Post/Story, process with Instagram_image handler
        logger.info("Detected Instagram Post/Story. Sending to get_instagram_content()...")
        return fetch_instagram_media(post_url)
