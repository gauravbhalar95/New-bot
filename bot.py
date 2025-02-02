import os
import logging
from flask import Flask, request
import telebot
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from utils.thumb_generator import generate_thumbnail
from config import API_TOKEN, PORT, WEBHOOK_URL

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be', 'instagram.com', 'x.com',
    'facebook.com', 'xvideos.com', 'xnxx.com', 'xhamster.com', 'pornhub.com']

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