import os
import gc
import logging
import threading
import asyncio
from flask import Flask, request
import telebot
from telethon import TelegramClient
from config import API_TOKEN, WEBHOOK_URL, PORT, API_ID, API_HASH
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import trim_video
from utils.sanitize import is_valid_url
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from telebot import types
from queue import Queue

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
logger = setup_logging()
queue = Queue()

# Create a new asyncio loop for Telethon
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Initialize Telethon client with the custom loop
client = TelegramClient('bot_session', API_ID, API_HASH, loop=loop)

async def main():
    await client.start(bot_token=API_TOKEN)
    print("Telethon client started")

loop.run_until_complete(main())

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
        file_path, file_size, thumbnail_path = download_video(url)
        if not file_path:
            bot.reply_to(message, "Error: Video download failed.")
            return
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")

        if file_size > 2 * 1024 * 1024 * 1024:  # If file size is greater than 2GB
            streaming_link = get_streaming_url(file_path)
            bot.send_message(message.chat.id, f"Video is too large to send. Stream it here: {streaming_link}")
        else:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
        bot.reply_to(message, "✅ Video sent successfully.")
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        bot.reply_to(message, f"❌ An error occurred: {str(e)}")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    threading.Thread(target=download_and_send_video, args=(message, url)).start()

# Flask app to keep bot alive and handle webhooks
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=PORT)