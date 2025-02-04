import os
import logging
from flask import Flask, request
import telebot
from config import API_TOKEN, PORT, WEBHOOK_URL
from handlers.common_handler import process_adult
from utils.thumb_generator import generate_thumbnail

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be', 'instagram.com', 'x.com', 'facebook.com',
    'xvideos.com', 'xnxx.com', 'xhamster.com', 'pornhub.com', 'redtube.com',
    'tube8.com', 'spankbang.com', 'youjizz.com', 'tnaflix.com', 'youporn.com',
    'brazzers.com', 'mofos.com', 'vivid.com', 'bangbros.com', 'clips4sale.com',
    'chaturbate.com', 'livejasmin.com', 'bongacams.com', 'myfreecams.com', 'cam4.com',
    'stripchat.com', 'femdomempire.com', 'naughtyamerica.com', 'hustler.com',
    'evolvedfights.com', 'fuckbook.com', 'xlovecam.com'
]

def detect_platform(url):
    """Detects if the URL belongs to a supported platform."""
    if any(domain in url for domain in SUPPORTED_DOMAINS):
        return "adult"
    return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Welcome! Send me a video link from supported sites to download.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    platform = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid video link.")
        return

    bot.reply_to(message, f"⏳ Downloading from {platform.capitalize()}... Please wait.")

    try:
        file_path, file_size = process_adult(url)

        if not file_path:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        # Ensure file is within Telegram's size limit
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
            bot.reply_to(message, "❌ File is too large to send on Telegram.")
            os.remove(file_path)
            return

        # Generate a thumbnail
        thumb_path = generate_thumbnail(file_path)

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

        # Cleanup
        os.remove(file_path)
        if thumb_path:
            os.remove(thumb_path)

        logger.info(f"✔ Video sent: {file_path}")

    except Exception as e:
        logger.error(f"⚠️ Error sending video: {e}")
        bot.reply_to(message, f"❌ Error processing your request: {str(e)}")

# Flask Webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
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