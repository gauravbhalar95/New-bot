import os
import gc
import logging
import asyncio
import requests
import telebot
import psutil
from queue import Queue
from telebot.async_telebot import AsyncTeleBot  # Async TeleBot Import
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging
from utils.streaming import get_streaming_url  # ✅ Streaming Module Use

# Setup logging
logger = setup_logging(logging.DEBUG)

# Initialize Async bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Queue for managing downloads
download_queue = Queue()

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

# 🔥 Monitor memory usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024)} MB")

# 📥 Background Download Handler (Async)
async def background_download(message, url):
    try:
        await bot.send_message(message.chat.id, "📥 **Download started. Please wait...**")
        logger.info(f"Processing URL: {url}")

        # Detect platform and get handler
        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Start download
        file_path, file_size, thumbnail_path = await handler(url)
        
        # ✅ Handle Large Files - Use Streaming
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            streaming_url = await get_streaming_url(url)
            if streaming_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File is too large for Telegram. Watch it online:** [Click Here]({streaming_url})",
                    disable_web_page_preview=True
                )
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed. Try again later.**")
            return

        log_memory_usage()

        # 🖼️ Send Thumbnail
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # 📤 Send Video
        with open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        # 🧹 Cleanup
        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# 🏁 Start Command
@bot.message_handler(commands=["start"])
async def start(message):
    await bot.reply_to(message, "👋 **Welcome!** Send me a video link, and I'll download it for you!")
    logger.info(f"User {message.chat.id} started the bot.")

# ✉️ Handle Incoming Messages
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    logger.info(f"Received message from {message.chat.id}: {url}")

    # Debugging response
    await bot.send_message(message.chat.id, f"🔍 Checking URL: {url}")

    # Run in a separate async task
    asyncio.create_task(background_download(message, url))

# 🚀 Run the bot
async def main():
    logger.info("Bot is starting...")
    await bot.infinity_polling()

if __name__ == "__main__":
    asyncio.run(main())