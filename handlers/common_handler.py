import os
import gc
import logging
import telebot
from queue import Queue
from threading import Thread
from urllib.parse import urlparse
from download.common_download import download_video, get_streaming_url

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
API_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Task queue
task_queue = Queue()

# Supported domains
SUPPORTED_DOMAINS = [
    'x.com',
    'facebook.com', 'xnxx.com', 'xhamster.com', 'pornhub.com'
]

# Validate URL function
def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ["http", "https"] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Handle video download task
def handle_download_task(url, message):
    file_path, file_size = download_video(url)

    if not file_path:
        bot.reply_to(message, "❌ Error: Video download failed. Ensure the URL is correct.")
        return

    try:
        # Check Telegram's file size limit (2GB)
        if file_size > 2 * 1024 * 1024 * 1024:
            streaming_url = get_streaming_url(url)
            if streaming_url:
                bot.reply_to(message, f"⚠️ The video is too large for Telegram.\n🔗 Streaming Link: {streaming_url}")
            else:
                bot.reply_to(message, "❌ Error: Unable to fetch a streaming link.")
        else:
            # Send the video
            with open(file_path, "rb") as video:
                bot.send_video(message.chat.id, video)

    except Exception as e:
        logger.error(f"Error sending video: {e}")
        streaming_url = get_streaming_url(url)
        if streaming_url:
            bot.reply_to(message, f"⚠️ Video is too large.\n🔗 Streaming Link: {streaming_url}")
        else:
            bot.reply_to(message, f"❌ Error: {e}")

    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        gc.collect()

# Worker function to process download tasks
def worker():
    while True:
        task = task_queue.get()
        if task is None:
            break
        url, message = task
        handle_download_task(url, message)
        task_queue.task_done()

# Start worker threads
for _ in range(4):  # Adjust the number of threads as needed
    Thread(target=worker, daemon=True).start()

# Handler for download requests
@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_message(message):
    url = message.text.strip()
    
    if not is_valid_url(url):
        bot.reply_to(message, "❌ Invalid or unsupported URL.")
        return

    bot.reply_to(message, "⏳ Processing your request. Please wait...")
    task_queue.put((url, message))
