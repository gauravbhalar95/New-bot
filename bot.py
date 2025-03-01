import os
import gc
import logging
import asyncio
import requests
import telebot
import psutil
import ffmpeg
from requests.exceptions import ConnectionError
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Importing project-specific modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.INFO)

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# API Key for api.video
API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"

# Supported platforms & handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,
    ),
}


# 🔍 Detect platform from URL
def detect_platform(url):
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None


# 🚀 **Optimize Video with FFmpeg**
async def compress_video(input_path, output_path):
    try:
        (
            ffmpeg.input(input_path)
            .output(output_path, vcodec="libx265", crf=28, preset="fast")
            .run(overwrite_output=True)
        )
        return output_path
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        return input_path


# 📥 **Asynchronous Download Handler**
async def async_download(message, url):
    try:
        bot.send_message(message.chat.id, "📥 **Download started. Please wait...**")

        # Detect platform and get handler
        platform, handler = detect_platform(url)
        if not handler:
            bot.send_message(message.chat.id, "⚠️ **Unsupported URL. Please provide a valid link.**")
            return

        # Start download (✅ Awaiting async function)
        file_path, file_size, thumbnail_path = await handler(url)

        if not file_path:
            bot.send_message(message.chat.id, "❌ **Download failed. Try again later.**")
            return

        # 🖼️ **Send Thumbnail**
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # 🏗️ **Handle Large Files**
        if file_size > TELEGRAM_FILE_LIMIT:
            bot.send_message(
                message.chat.id,
                "⚠️ **File is too large for Telegram (50MB limit). Try downloading a lower-resolution version.**",
            )
            return

        # 🎥 **Optimize Video Before Sending**
        compressed_path = await compress_video(file_path, file_path.replace(".mp4", "_compressed.mp4"))

        # 📤 **Send Video**
        with open(compressed_path, "rb") as video:
            bot.send_video(message.chat.id, video, supports_streaming=True)

        # 🧹 **Cleanup**
        for path in [file_path, compressed_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")


# 🏁 **Start Command**
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "👋 **Welcome!** Send me a video link, and I'll download it for you!",
    )


# ✉️ **Handle Incoming Messages Asynchronously**
@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_message(message):
    url = message.text.strip()
    asyncio.create_task(async_download(message, url))  # ✅ Non-blocking async execution


# 🚀 Run the bot
if __name__ == "__main__":
    bot.infinity_polling()