import os
import gc
import logging
import asyncio
import requests
import telebot
import psutil
from queue import Queue
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.mega_handlers import MegaNZ  # ✅ Mega.nz Import
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging
from utils.streaming import get_streaming_url

logger = setup_logging(logging.DEBUG)
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
mega = MegaNZ()
download_queue = Queue()

API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"

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

def detect_platform(url):
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024)} MB")

async def background_download(message, url):
    try:
        await bot.send_message(message.chat.id, "📥 **Download started...**")
        logger.info(f"Processing URL: {url}")

        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        file_path, file_size, thumbnail_path = await handler(url)

        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            streaming_url = await get_streaming_url(url)
            if streaming_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Watch here:** [Click]({streaming_url})",
                    disable_web_page_preview=True
                )
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        log_memory_usage()

        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        with open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

@bot.message_handler(commands=["meganz"])
async def login_mega(message):
    args = message.text.split()[1:]
    if len(args) < 2:
        await bot.send_message(message.chat.id, "❌ Usage: `/meganz <username> <password>`")
        return

    username, password = args
    msg = await mega.login(username, password)  # Async login function
    await bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=["mega"])
async def mega_upload(message):
    args = message.text.split()[1:]
    if len(args) < 1:
        await bot.send_message(message.chat.id, "❌ Usage: `/mega <url> [folder]`")
        return

    url = args[0]
    folder = args[1] if len(args) > 1 else None

    file_path, msg = await mega.download_from_url(url, folder)
    await bot.send_message(message.chat.id, msg)

    if file_path:
        link, msg = await mega.upload_to_mega(file_path)
        await bot.send_message(message.chat.id, f"✅ Uploaded to Mega.nz: {link}")

@bot.message_handler(commands=["start"])
async def start(message):
    await bot.reply_to(message, "👋 **Welcome!** Send me a video link or use `/meganz` to login to Mega.nz.")
    logger.info(f"User {message.chat.id} started the bot.")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    logger.info(f"Received message from {message.chat.id}: {url}")
    await bot.send_message(message.chat.id, f"🔍 Checking URL: {url}")
    asyncio.create_task(background_download(message, url))

async def main():
    logger.info("Bot is starting...")
    await bot.infinity_polling()

if __name__ == "__main__":
    asyncio.run(main())