import os
import logging
from flask import Flask, request
import telebot
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from config import API_TOKEN, WEBHOOK_URL, PORT

# ✅ Initialize bot in webhook mode (no polling)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ Supported domains
SUPPORTED_DOMAINS = {
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
    "twitter": ["x.com", "twitter.com"],
    "adult": ["xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com", "redtube.com", 
              "tube8.com", "spankbang.com"]
}

def detect_platform(url):
    """Detects the platform from the URL."""
    for platform, domains in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform
    return None

@bot.message_handler(commands=['start'])
def start(message):
    """Start command handler."""
    bot.reply_to(message, "👋 Welcome! Send me a YouTube, Instagram, Twitter (X), or adult site link to download.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handles incoming messages and processes the URLs."""
    url = message.text.strip()
    platform = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid link.")
        return

    bot.reply_to(message, f"⏳ Downloading from {platform.capitalize()}... Please wait.")

    try:
        # ✅ Process based on platform type
        process_funcs = {
            "youtube": process_youtube,
            "instagram": process_instagram,
            "adult": lambda url: process_adult(url, message.chat.id),
            "twitter": lambda url: download_twitter_media(url, message.chat.id)
        }
        result = process_funcs.get(platform, lambda _: None)(url)

        if not result:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        # ✅ Handle different return values properly
        if isinstance(result, tuple) and len(result) in [2, 3]:
            file_path, file_size = result[:2]
            thumb_path = result[2] if len(result) == 3 else None
        else:
            bot.reply_to(message, "❌ Unexpected response from the downloader.")
            return

        # ✅ Ensure file exists before sending
        if not os.path.exists(file_path):
            bot.reply_to(message, "❌ Error: File not found.")
            return

        # ✅ Send video with optional thumbnail
        with open(file_path, 'rb') as video:
            thumb = open(thumb_path, 'rb') if thumb_path and os.path.exists(thumb_path) else None
            bot.send_video(
                message.chat.id,
                video,
                thumb=thumb,
                caption=f"✅ Download complete! File size: {file_size / (1024 * 1024):.2f} MB"
            )
            if thumb:
                thumb.close()

        logger.info(f"✔ Video sent: {file_path}")

    except Exception as e:
        logger.error(f"⚠️ Error sending video: {e}")
        bot.reply_to(message, f"❌ Error processing your request. {str(e)}")

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    """Webhook to process new updates."""
    try:
        bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook error: {e}")
        return "ERROR", 500

@app.route('/')
def set_webhook():
    """Set the webhook for Telegram."""
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
        return "Webhook set", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook setup error: {e}")
        return "ERROR", 500

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=PORT)