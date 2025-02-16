import os
import gc
import logging
import threading
from flask import Flask, request
import telebot
from config import API_TOKEN, WEBHOOK_URL, PORT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import is_valid_url
from utils.logger import setup_logging
from telebot import types
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
    return None, None

def get_streaming_url(url):
    return f"https://stream.example.com?url={url}"  # Replace with actual service

def download_video(url):
    platform, handler = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported platform")
    return handler(url)  # Call appropriate handler

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

def download_and_send_video(message, url):
    try:
        if not is_valid_url(url):
            bot.reply_to(message, "Invalid or unsupported URL.")
            return
        bot.reply_to(message, "Downloading video, please wait...")
        file_path, file_size = download_video(url)
        if not file_path:
            bot.reply_to(message, "Error: Video download failed.")
            return
        if file_size > 2 * 1024 * 1024 * 1024:
            bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{get_streaming_url(url)}")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
        os.remove(file_path)
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

app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    try:
        logger.info("Webhook received.")
        bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return "Error", 500

@app.route('/')
def set_webhook():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
        logger.info("Webhook set successfully.")
        return "Webhook set", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Error setting webhook: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(PORT))