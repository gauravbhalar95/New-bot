import os
import gc
import logging
import threading
import telebot
import requests
import yt_dlp  # Added for streaming link
import psutil  # To monitor memory usage
import time
from queue import Queue
from requests.exceptions import ConnectionError

from config import API_TOKEN, COOKIES_FILE
from handlers.youtube_handler import process_youtube
from handlers.Instagram_image import get_instagram_content
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.facebook_handlers import process_facebook
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)

# API Key for video uploads
API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
queue = Queue()

# Supported domains and their handlers
SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram, get_instagram_content),
    "facebook": (["facebook.com"], process_facebook),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),
}

def detect_platform(url):
    for platform, values in SUPPORTED_DOMAINS.items():
        domains, *handlers = values
        if any(domain in url for domain in domains):
            if platform == "instagram":
                if "/stories/" in url:
                    return platform, (get_instagram_content,)
                return platform, (process_instagram,)
            return platform, handlers
    return None, None

# Fetch a streaming URL without downloading the video
def get_streaming_url(url):
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

# Upload video to API.video
def upload_to_api_video(file_path):
    url = "https://ws.api.video/videos"
    headers = {"Authorization": f"Bearer {API_VIDEO_KEY}"}
    files = {'file': open(file_path, 'rb')}
    data = {'title': os.path.basename(file_path)}
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 201:
        return response.json()['assets']['player']
    else:
        raise Exception("Failed to upload video to api.video")

# Retry mechanism for requests
def send_request_with_retries(url, payload, retries=5, delay=3):
    for attempt in range(retries):
        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                return response
            else:
                logger.error(f"Unexpected status code {response.status_code}")
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            if attempt < retries - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error("Max retries reached. Request failed.")
    return None

# Download video based on platform handler
def download_video(url):
    platform, handlers = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported platform")
    return handlers[0](url)

# Log memory usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024)} MB")

# Start command
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

# Download and send video
def download_and_send_video(message, url):
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

        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")

        if file_size > 50 * 1024 * 1024:  # 50MB limit for Telegram
            streaming_link = get_streaming_url(url)
            if streaming_link:
                bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{streaming_link}")
            else:
                bot.reply_to(message, "Failed to get streaming link.")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)

        if os.path.exists(file_path):
            os.remove(file_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"Error occurred: {e}")

# Worker thread for processing download queue
def worker():
    while True:
        message, url = queue.get()
        if message == "STOP":
            break
        download_and_send_video(message, url)
        queue.task_done()

# Handle incoming messages
def handle_message(message):
    queue.put((message, message.text.strip()))

# Register command and message handlers
bot.message_handler(commands=['start'])(start)
bot.message_handler(func=lambda message: True, content_types=['text'])(handle_message)

# Start worker thread
threading.Thread(target=worker, daemon=True).start()
