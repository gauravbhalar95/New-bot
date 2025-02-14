import os
import logging
import telebot
import yt_dlp
import re
from urllib.parse import urlparse
import gc  # Garbage collection for memory cleanup
from config import DOWNLOAD_DIR, API_TOKEN, INSTAGRAM_FILE
from utils.sanitize import is_valid_url  # Sanitization utility

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = [
    'instagram.com'
]

# Validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Process Instagram video download
def process_instagram(url, chat_id):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0)
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {e}")
        return None, 0

