import os
import gc
import logging
import threading
import telebot
import requests
import yt_dlp  # For streaming link
import psutil  # To monitor memory usage
import time
from queue import Queue
from requests.exceptions import ConnectionError

from config import API_TOKEN, COOKIES_FILE
from handlers.youtube_handler import process_youtube
from handlers.Instagram_image import process_instagram_post
from handlers.instagram_handler import handle_instagram_url
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.facebook_handlers import process_facebook
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.DEBUG)

# Initialize Telegram bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
queue = Queue()

# API Video Key
API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"

# Supported platforms
SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], handle_instagram_url, process_instagram_post),
    "facebook": (["facebook.com"], process_facebook),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),
}

def detect_platform(url):
    """Detect the platform based on the URL."""
    for platform, values in SUPPORTED_DOMAINS.items():
        domains, *handlers = values
        if any(domain in url for domain in domains):
            if platform == "instagram":
                if "/reel/" in url or "/reels/" in url:
                    return platform, (handle_instagram_url,)  # For Instagram reels
                return platform, (process_instagram_post(url),)  # For Instagram posts & stories
            return platform, handlers
    return None, None

def get_streaming_url(url):
    """Fetch a streaming URL without downloading the video."""
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'cookiefile': COOKIES_FILE,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get('url')
    except Exception as e:
        logger.error(f"Error fetching streaming URL: {e}")
        return None

def upload_to_api_video(file_path):
    """Upload video to API Video service."""
    url = "https://ws.api.video/videos"
    headers = {"Authorization": f"Bearer {API_VIDEO_KEY}"}
    with open(file_path, 'rb') as file:
        files = {'file': file}
        data = {'title': os.path.basename(file_path)}
        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 201:
        return response.json()['assets']['player']
    
    raise Exception("Failed to upload video to api.video")

def send_request_with_retries(url, payload, retries=5, delay=3):
    """Send a request with retries in case of failures."""
    for attempt in range(retries):
        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                return response
            logger.error(f"Unexpected status code: {response.status_code}")
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
        
        if attempt < retries - 1:
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    logger.error("Max retries reached. Request failed.")
    return None

def download_video(url):
    """Download video based on the detected platform."""
    platform, handlers = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported platform")
    
    return handlers[0]  # Execute the first handler function

def log_memory_usage():
    """Log system memory usage."""
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024):.2f} MB")

@bot.message_handler(commands=['start'])
def start(message):
    """Handle /start command."""
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

def download_and_send_video(message, url):
    """Download and send video to the user."""
    try:
        if not sanitize_filename(url):
            bot.reply_to(message, "Invalid or unsupported URL.")
            return

        bot.reply_to(message, "Downloading video, please wait...")
        log_memory_usage()

        file_path, file_size, thumbnail_path = download_video(url)

        if not file_path:
            bot.reply_to(message, "Error: Video download failed.")
            return

        log_memory_usage()

        # Send thumbnail if available
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")

        # Check file size for Telegram limits
        if file_size > 50 * 1024 * 1024:  # 50MB limit for Telegram
            streaming_link = get_streaming_url(url)
            if streaming_link:
                bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{streaming_link}")
            else:
                bot.reply_to(message, "Failed to get streaming link.")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)

        # Cleanup files
        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"Error occurred: {e}")

def worker():
    """Worker thread to process video downloads."""
    while True:
        message, url = queue.get()
        if message == "STOP":
            break
        download_and_send_video(message, url)
        queue.task_done()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handle incoming messages."""
    parts = message.text.strip().split()