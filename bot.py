import os
import gc
import logging
import threading
import telebot
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import is_valid_url
from utils.logger import setup_logging
from queue import Queue

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
logger = setup_logging()
queue = Queue()

SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),
}

def detect_platform(url):
    for platform, (domains, handler) in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None  # Return only two values


def get_streaming_url(url):
    return f"https://stream.example.com?url={url}"  # Replace with actual service

def download_video(url):
    platform, handler = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported platform")
    return handler(url)  # Ensure this returns two values (e.g., file_path, file_size)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

def download_and_send_video(message, url):
    try:
        if not is_valid_url(url):
            bot.reply_to(message, "Invalid or unsupported URL.")
            return
        bot.reply_to(message, "Downloading video, please wait...")
        file_path, file_size, thumbnail_path = download_video(url)
        if not file_path:
            bot.reply_to(message, "Error: Video download failed.")
            return
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")

        if file_size > 100 * 1024 * 1024:  # If file size is greater than 2GB
            bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{get_streaming_url(url)}")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)

        if os.path.exists(file_path):
            os.remove(file_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"Error occurred: {e}")

def worker():
    while True:
        message, url = queue.get()
        if message == "STOP":
            break
        download_and_send_video(message, url)
        queue.task_done()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    queue.put((message, message.text.strip()))

threading.Thread(target=worker, daemon=True).start()