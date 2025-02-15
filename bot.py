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
from utils.thumb_generator import generate_thumbnail, download_video
from telebot import types

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
logger = setup_logging()

SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),
}

def detect_platform(url):
    """Detect the platform based on the provided URL."""
    for platform, (domains, handler) in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

def get_streaming_url(url):
    """Generate a streaming link for large videos."""
    return f"https://stream.example.com?url={url}"  # Replace with actual streaming service

@bot.message_handler(commands=['start'])
def start(message):
    """Handle the /start command."""
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

def process_video(message, url):
    """Download and send video, or provide streaming link for large files."""
    if not is_valid_url(url):
        bot.reply_to(message, "Invalid or unsupported URL.")
        return
    
    bot.reply_to(message, "Downloading video, please wait...")
    file_path, file_size = download_video(url)
    
    if not file_path:
        bot.reply_to(message, "Error: Video download failed.")
        return

    try:
        if file_size > 2 * 1024 * 1024 * 1024:  # If file > 2GB
            streaming_url = get_streaming_url(url)
            if streaming_url:
                bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{streaming_url}")
            else:
                bot.reply_to(message, "Unable to fetch a streaming link.")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        streaming_url = get_streaming_url(url)
        if streaming_url:
            bot.reply_to(message, f"Video too large. Stream here:\n{streaming_url}")
        else:
            bot.reply_to(message, f"Error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        gc.collect()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handle text messages by detecting the platform and processing the video."""
    url = message.text.strip()
    threading.Thread(target=process_video, args=(message, url)).start()  # Run in a separate thread

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    """Process new updates from Telegram."""
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    """Set the webhook for Telegram bot."""
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)