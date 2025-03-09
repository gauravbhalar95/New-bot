import os
import gc
import logging
import asyncio
import aiofiles
import requests
import telebot
import psutil
import subprocess
from queue import Queue
from flask import Flask, request, jsonify
from telebot.async_telebot import AsyncTeleBot
from dotenv import load_dotenv

from config import API_TOKEN, TELEGRAM_FILE_LIMIT, WEBHOOK_URL, PORT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.mega_handlers import MegaNZ  
from utils.logger import setup_logging
from utils.streaming import get_streaming_url, ApiVideoClient, download_best_clip

# Load environment variables
load_dotenv()

# Logging setup
logger = setup_logging(logging.DEBUG)

# Flask app for webhook
app = Flask(__name__)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
mega = MegaNZ()
download_queue = asyncio.Queue()

# Track active downloads per user
active_downloads = {}

# Supported platforms and handlers
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
    """Detects the platform of the given URL and returns the corresponding handler function."""
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# Log memory usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024):.2f} MB")

# Function to retry failed downloads
async def retry_download(handler, url, retries=3):
    """Retries a failed download up to 3 times before failing."""
    for attempt in range(retries):
        try:
            return await handler(url)
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(2)
    return None  # Return None if all retries fail

# Background download function
async def background_download(message, url):
    """Handles the entire download process and sends the video to Telegram."""
    chat_id = message.chat.id
    active_downloads[chat_id] = {"url": url, "status": "Downloading"}

    try:
        await bot.send_message(chat_id, "📥 **Download started...**")
        logger.info(f"Processing URL: {url}")

        platform, handler = detect_platform(url)
        if not handler:
            active_downloads[chat_id]["status"] = "Failed: Unsupported URL"
            await bot.send_message(chat_id, "⚠️ **Unsupported URL.**")
            return

        task = asyncio.create_task(retry_download(handler, url))
        result = await task

        if not result:
            active_downloads[chat_id]["status"] = "Failed: Download Error"
            await bot.send_message(chat_id, "❌ **Download failed after multiple attempts.**")
            return

        if isinstance(result, tuple) and len(result) >= 3:
            file_path, file_size, streaming_url = result[:3]
            thumbnail_path = result[3] if len(result) > 3 else None
        else:
            active_downloads[chat_id]["status"] = "Failed: Processing Error"
            await bot.send_message(chat_id, "❌ **Error processing video.**")
            return

        file_size = int(file_size)
        telegram_limit = int(TELEGRAM_FILE_LIMIT)

        if not file_path or file_size > telegram_limit:
            video_url, duration = await get_streaming_url(url)

            if video_url:
                active_downloads[chat_id]["status"] = "Completed (Streaming Link)"
                await bot.send_message(
                    chat_id,
                    f"⚡ **File too large for Telegram. Watch here:** [Click]({video_url})",
                    disable_web_page_preview=True
                )

                if handler == process_adult:
                    clip_path = await download_best_clip(video_url, int(duration))
                    if clip_path:
                        async with aiofiles.open(clip_path, "rb") as clip:
                            await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
                        os.remove(clip_path)
            else:
                active_downloads[chat_id]["status"] = "Failed: Streaming Error"
                await bot.send_message(chat_id, "❌ **Download failed.**")
            return

        log_memory_usage()

        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(chat_id, thumb, caption="✅ **Thumbnail received!**")

        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(chat_id, video, supports_streaming=True)

        active_downloads[chat_id]["status"] = "Completed"

        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        active_downloads[chat_id]["status"] = f"Failed: {str(e)}"
        logger.error(f"Error: {e}")
        await bot.send_message(chat_id, f"❌ **An error occurred:** `{e}`")

# Worker function for parallel downloads
async def worker():
    """Processes multiple downloads in parallel (up to 3 at a time)."""
    while True:
        queue_items = []
        while not download_queue.empty() and len(queue_items) < 3:
            queue_items.append(await download_queue.get())

        if queue_items:
            tasks = [asyncio.create_task(background_download(msg, url)) for msg, url in queue_items]
            await asyncio.gather(*tasks)

            for _ in queue_items:
                download_queue.task_done()

@bot.message_handler(commands=["start"])
async def start(message):
    """Sends a welcome message to the user."""
    user_name = message.from_user.first_name or "User"
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link or use `/meganz` to login to Mega.nz."
    await bot.reply_to(message, welcome_text)
    logger.info(f"User {message.chat.id} started the bot.")

@bot.message_handler(commands=["status"])
async def check_status(message):
    """Checks the download status for the user."""
    chat_id = message.chat.id
    if chat_id in active_downloads:
        status = active_downloads[chat_id]
        await bot.send_message(chat_id, f"📊 **Your Download Status:**\n\n🔗 URL: {status['url']}\n⚡ Status: {status['status']}")
    else:
        await bot.send_message(chat_id, "❌ **No active downloads found.**")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles incoming messages and adds them to the download queue."""
    url = message.text.strip()
    await download_queue.put((message, url))
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")

async def main():
    """Starts the bot in polling mode (use this for local testing)."""
    logger.info("Bot is starting in polling mode...")
    worker_task = asyncio.create_task(worker())
    await asyncio.gather(bot.infinity_polling(), worker_task)

if __name__ == "__main__":
    asyncio.run(main())  # Run in polling mode