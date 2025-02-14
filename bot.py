# bot.py
import os
import gc
import logging
from flask import Flask, request, jsonify
import telebot
from config import API_TOKEN, WEBHOOK_URL, PORT  # Make sure this points to your config file
from handlers.youtube_handler import process_youtube  # Example, adjust imports as needed
from handlers.instagram_handler import process_instagram # Example
from handlers.common_handler import process_adult #Example
from handlers.x_handler import download_twitter_media #Example
# ... (your other imports if any)

# Bot setup
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Supported Domains
SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),  # Using "x" for Twitter
    "adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xhamster43.desi", "xnxx.com", "youporn.com"], # Example placeholders. Replace with actual domains.
        process_adult, # Ensure this handles different sites appropriately
    ),
}

# Platform Detection
def detect_platform(url):
    for platform, (domains, handler) in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# Command: /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")

# Handle video download and optional streaming
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    if not is_valid_url(url):
        bot.reply_to(message, "Invalid or unsupported URL.")
        return

    bot.reply_to(message, "Downloading video, please wait...")
    file_path, file_size = download_video(url)

    if not file_path:
        bot.reply_to(message, "Error: Video download failed. Ensure the URL is correct.")
        return

    try:
        # Check if the file size exceeds Telegram's limit (2GB)
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB in bytes
            streaming_url = get_streaming_url(url)
            if streaming_url:
                bot.reply_to(
                    message,
                    f"The video is too large to send on Telegram. Here is the streaming link:\n{streaming_url}"
                )
            else:
                bot.reply_to(message, "Error: Unable to fetch a streaming link for this video.")
        else:
            # Try sending the video
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        # If the video is too large, provide streaming link instead
        streaming_url = get_streaming_url(url)
        if streaming_url:
            bot.reply_to(
                message,
                f"The video is too large to send directly on Telegram. Here is the streaming link:\n{streaming_url}"
            )
        else:
            bot.reply_to(message, f"Error: {e}")
    finally:
        # Clean up the downloaded file and memory
        if os.path.exists(file_path):
            os.remove(file_path)
        # Free up memory by triggering garbage collection
        gc.collect()

# Flask app for webhook
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