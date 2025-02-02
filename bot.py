import os
import logging
from flask import Flask, request
import telebot
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from utils.thumb_generator import generate_thumbnail
from config import API_TOKEN

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = ["youtube.com", "youtu.be", "instagram.com", "x.com"]

def detect_platform(url):
    """Detects if the URL belongs to YouTube, Instagram, or other supported platforms."""
    if any(domain in url for domain in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif "instagram.com" in url:
        return "instagram"
    else:
        return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Welcome! Send me a YouTube or Instagram link to download.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    platform = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid YouTube or Instagram link.")
        return

    bot.reply_to(message, f"⏳ Downloading from {platform.capitalize()}... Please wait.")

    try:
        if platform == "youtube":
            file_path, file_size, thumb_path = process_youtube(url)
        elif platform == "instagram":
            file_path, file_size, thumb_path = process_instagram(url)
        
        if not file_path:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        # Send video with a thumbnail if available
        with open(file_path, 'rb') as video:
            thumb = open(thumb_path, 'rb') if thumb_path else None
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

# Flask Webhook
app = Flask(__name__)

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    success = bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    return "Webhook set" if success else "Webhook failed", 200

if __name__ == '__main__':
    logger.info(f"🚀 Starting bot on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT)