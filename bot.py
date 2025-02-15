import os
import gc
import logging
import threading
import multiprocessing
from flask import Flask, request
import telebot
from config import API_TOKEN, WEBHOOK_URL, PORT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import is_valid_url
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from telebot import types
from queue import Queue

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
logger = setup_logging()

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
    return None, None

def get_streaming_url(url):
    """Generate a streaming link for large videos."""
    return f"https://stream.example.com?url={url}"  # Replace with your actual streaming service

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

def download_and_send_video(message, url, queue):
    if not is_valid_url(url):
        queue.put((message, "Invalid or unsupported URL."))
        return
    
    queue.put((message, "Downloading video, please wait..."))
    file_path, file_size = download_video(url)
    
    if not file_path:
        queue.put((message, "Error: Video download failed."))
        return

    try:
        if file_size > 2 * 1024 * 1024 * 1024:  # File larger than 2GB
            streaming_url = get_streaming_url(url)
            if streaming_url:
                queue.put((message, f"Video too large for Telegram. Stream here:\n{streaming_url}"))
            else:
                queue.put((message, "Unable to fetch a streaming link."))
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        streaming_url = get_streaming_url(url)
        if streaming_url:
            queue.put((message, f"Video too large. Stream here:\n{streaming_url}"))
        else:
            queue.put((message, f"Error: {e}"))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        gc.collect()

def worker(queue):
    while True:
        message, url = queue.get()
        if message == "STOP":
            break
        try:
            download_and_send_video(message, url, queue)
        except Exception as e:
            logger.error(f"Error in worker process: {e}")
        queue.task_done()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    queue.put((message, url))

# Create and start worker processes
queue = Queue()
num_workers = multiprocessing.cpu_count()  # Use all available CPU cores
processes = []
for i in range(num_workers):
    p = multiprocessing.Process(target=worker, args=(queue,))
    p.start()
    processes.append(p)

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=PORT)
    finally:
        for _ in range(num_workers):
            queue.put(("STOP", None))
        for p in processes:
            p.join()