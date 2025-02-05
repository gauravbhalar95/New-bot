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
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be', 'instagram.com', 'xvideos.com', 'xnxx.com',
    'xhamster.com', 'pornhub.com', 'redtube.com', 'x.com', 'tube8.com', 'spankbang.com'
]

def detect_platform(url):
    """Detects if the URL is from YouTube, Instagram, or other supported sites."""
    if any(domain in url for domain in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif "instagram.com" in url:
        return "instagram"
    elif any(domain in url for domain in SUPPORTED_DOMAINS):
        return "adult"
    else:
        return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Welcome! Send me a YouTube, Instagram, or adult site link to download.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    platform = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid YouTube, Instagram, or supported adult site link.")
        return

    bot.reply_to(message, f"⏳ Downloading from {platform.capitalize()}... Please wait.")

    try:
        if platform == "youtube":
            result = process_youtube(url)
        elif platform == "instagram":
            result = process_instagram(url)
        elif platform == "adult":
            result = process_adult(url)
        elif platform == "instaloader":
            result = extract_shortcode(url)
        elif platform == "twitter":
            result = download_twitter_media(url)

        if not result:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        file_path, file_size, thumb_path = result if len(result) == 3 else (*result, None)

        # ✅ Send video with thumbnail if available
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

# ✅ Flask Webhook Setup
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    """First remove the webhook, then set a new one."""
    bot.remove_webhook()
    logger.info("🔄 Webhook removed.")
    
    success = bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    
    if success:
        logger.info(f"✅ Webhook set to {WEBHOOK_URL}/{API_TOKEN}")
        return "Webhook set successfully", 200
    else:
        logger.error("❌ Failed to set webhook.")
        return "Webhook failed", 500

if __name__ == '__main__':
    logger.info(f"🚀 Starting bot on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT)