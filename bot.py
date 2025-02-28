import os
import gc
import logging
import threading
import requests
import yt_dlp
import telebot
import psutil
import time
from queue import Queue
from requests.exceptions import ConnectionError
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Importing project-specific modules
from config import API_TOKEN, COOKIES_FILE, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging
from utils.streaming import get_streaming_url

# Setting up logging
logger = setup_logging(logging.DEBUG)

# API Key for api.video
API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
queue = Queue()

# Supported domains mapping
SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram),
    "facebook": (["facebook.com"], process_facebook),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),
}

# Detect platform from URL
def detect_platform(url):
    for platform, values in SUPPORTED_DOMAINS.items():
        domains, *handlers = values
        if any(domain in url for domain in domains):
            return platform, handlers
    return None, None

# Upload video to api.video
def upload_to_api_video(file_path):
    url = "https://ws.api.video/videos"
    headers = {"Authorization": f"Bearer {API_VIDEO_KEY}"}
    files = {'file': open(file_path, 'rb')}
    data = {'title': os.path.basename(file_path)}

    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 201:
        return response.json()['assets']['player']
    
    raise Exception("Failed to upload video to api.video")

# Send request with retries
def send_request_with_retries(url, payload, retries=5, delay=3):
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
            else:
                logger.error("Max retries reached. Request failed.")
    return None

# Download video based on platform
def download_video(url):
    platform, handlers = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported platform")

    for handler in handlers:
        if callable(handler):
            return handler(url)
    return None

# Log memory usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024)} MB")

# Handle /start command
@bot.message_handler(commands=['start'])
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

        # Send thumbnail if available
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")

        # Handle large files
        if file_size > TELEGRAM_FILE_LIMIT:
            streaming_link = get_streaming_url(url)
            if streaming_link:
                download_button = InlineKeyboardMarkup()
                download_button.add(
                    InlineKeyboardButton("🔽 Download Video", url=streaming_link)
                )
                bot.send_message(
                    message.chat.id,
                    f"⚡ Video is too large for Telegram.\n\n🎥 **Watch it here:** {streaming_link}",
                    parse_mode="Markdown",
                    reply_markup=download_button
                )
            else:
                bot.reply_to(message, "Failed to get streaming link.")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video, supports_streaming=True)

        # Cleanup files
        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"Error occurred: {e}")

# Worker function to process download queue
def worker():
    while True:
        message, url = queue.get()
        if message == "STOP":
            break
        download_and_send_video(message, url)
        queue.task_done()

# Handle text messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    queue.put((message, message.text.strip()))

# Start worker thread
threading.Thread(target=worker, daemon=True).start()

# Run bot
if __name__ == "__main__":
    bot.infinity_polling()