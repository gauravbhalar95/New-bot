# bot.py
import os
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

# Message Handler
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    platform, handler = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid link.")
        return

    bot.reply_to(message, f"⏳ Processing {platform.capitalize()}... Please wait.")

    try:
        result = handler(url) # Call the handler for that platform

        if not result:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        if isinstance(result, tuple) and len(result) in [2, 3]:  # Check for tuple result
            file_path, file_size = result[:2]
            thumb_path = result[2] if len(result) == 3 else None
        else:
            bot.reply_to(message, "❌ Unexpected response from the downloader.") # Important for debugging
            return

        if not os.path.exists(file_path): # Check if the file exists after download
            bot.reply_to(message, "❌ Error: File not found.")
            return
        
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

        os.remove(file_path) # Clean up
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path) # Clean up the thumbnail as well

    except Exception as e:
        logger.exception(f"⚠️ Error processing request: {e}")  # Log full exception
        bot.reply_to(message, f"❌ Error: {type(e).__name__}: {str(e)}")  # User-friendly error

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