import os
import gc
import logging
from flask import Flask, request
import telebot
from config import API_TOKEN, WEBHOOK_URL, PORT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import is_valid_url
from utils.logger import setup_logging
from utils.thumb_generator important generate_thumbnail, download_video

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
logger = setup_logger()

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

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    if not is_valid_url(url):
        bot.reply_to(message, "Invalid or unsupported URL.")
        return
    bot.reply_to(message, "Downloading video, please wait...")
    file_path, file_size = download_video(url)
    if not file_path:
        bot.reply_to(message, "Error: Video download failed.")
        return
    try:
        if file_size > 2 * 1024 * 1024 * 1024:
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

app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)