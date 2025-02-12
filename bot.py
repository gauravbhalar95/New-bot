import os
import logging
from flask import Flask, request
import telebot
from config import API_TOKEN, WEBHOOK_URL
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media

PORT = int(os.getenv("PORT", 8080))
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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
    for platform, (domains, handler) in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
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

        os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)