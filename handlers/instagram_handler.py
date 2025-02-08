import os
import telebot
import yt_dlp
import logging
import re
from urllib.parse import urlparse
import time
import nest_asyncio
import gc  # Import garbage collection for memory cleanup
from config import DOWNLOAD_DIR, API_TOKEN, YOUTUBE_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from utils.sanitize import sanitize_filename

# Apply the patch for nested event loops
nest_asyncio.apply()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Supported domains
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be', 'instagram.com', 'x.com',
    'facebook.com', 'xvideos.com', 'xnxx.com', 'xhamster.com', 'pornhub.com'
]

# Utility to sanitize filenames
def sanitize_filename(filename, max_length=250):
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.strip()[:max_length]

# Validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Get streaming URL using yt-dlp
def get_streaming_url(url):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get('url')
    except Exception as e:
        logger.error(f"Error fetching streaming URL: {e}")
        return None

# Download Instagram video using yt-dlp
def process_instagram(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'username': INSTAGRAM_USERNAME,
        'password': INSTAGRAM_PASSWORD,
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,  # Add logger to yt-dlp options
        'verbose': True,  # Enable verbose logging
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0)
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0