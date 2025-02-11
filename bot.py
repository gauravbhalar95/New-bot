import os
import logging
import telebot
from config import API_TOKEN
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ Supported domains and their handlers
SUPPORTED_DOMAINS = {
    "youtube": (["youtube.com", "youtu.be"], process_youtube),
    "instagram": (["instagram.com"], process_instagram),
    "twitter": (["x.com", "twitter.com"], download_twitter_media),
    "adult": (
        ["xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com", "redtube.com", "tube8.com", "spankbang.com"],
        process_adult,
    ),
}

def detect_platform(url):
    """Detects the platform from the URL and returns the corresponding handler."""
    for platform, (domains, handler) in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# ✅ Handle Incoming Messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handles incoming messages and processes the URLs."""
    url = message.text.strip()
    platform, handler = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid link.")
        return

    bot.reply_to(message, f"⏳ Processing {platform.capitalize()}... Please wait.")

    try:
        result = handler(url, message.chat.id)

        if not result:
            bot.reply_to(message, "❌ Download failed. Please try again later.")
            return

        if isinstance(result, tuple) and len(result) in [2, 3]:
            file_path, file_size = result[:2]
            thumb_path = result[2] if len(result) == 3 else None
        else:
            bot.reply_to(message, "❌ Unexpected response from the downloader.")
            return

        if not os.path.exists(file_path):
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

        # ✅ Cleanup after sending
        os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")