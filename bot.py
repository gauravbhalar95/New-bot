import os
import gc
import logging
import asyncio
import aiofiles
import requests
import telebot
import psutil
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube_with_timestamps
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging
from utils.streaming import *
from utils.thumb_generator import *

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Supported platforms and handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube_with_timestamps),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,
    ),
}

def trim_youtube_url(url):
    """Trim YouTube URL to remove start and end time, or extract it."""
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Check for start and end time in query parameters
        start_time = query_params.get("start", [None])[0]
        end_time = query_params.get("end", [None])[0]

        # Build a trimmed URL
        trimmed_query = {k: v for k, v in query_params.items() if k not in ["start", "end"]}
        trimmed_url = urlunparse(parsed_url._replace(query=urlencode(trimmed_query, doseq=True)))

        return {
            "trimmed_url": trimmed_url,
            "start_time": start_time,
            "end_time": end_time,
        }
    except Exception as e:
        logger.error(f"Failed to trim YouTube URL: {e}")
        return None

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

# Background download function
async def background_download(message, url):
    """Handles the entire download process and sends the video to Telegram."""
    try:
        await bot.send_message(message.chat.id, "📥 **Download started...**")
        logger.info(f"Processing URL: {url}")

        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Trim YouTube URL and extract timestamps
        trimmed_data = trim_youtube_url(url) if platform == "YouTube" else None
        trimmed_url = trimmed_data["trimmed_url"] if trimmed_data else url
        start_time = trimmed_data["start_time"] if trimmed_data else None
        end_time = trimmed_data["end_time"] if trimmed_data else None

        # Call handler with timestamps if applicable
        task = asyncio.create_task(handler(trimmed_url, start_time=start_time, end_time=end_time))
        result = await task

        # Rest of your existing download logic...
        if result:
            # Handle your file processing and sending logic here
            pass

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# Worker function for parallel downloads
async def worker():
    while True:
        message, url = await download_queue.get()
        await background_download(message, url)
        download_queue.task_done()

# Main async function
async def main():
    """Starts the bot with 3 parallel download workers."""
    logger.info("Bot is starting...")

    # Start 3 parallel workers
    worker_tasks = [asyncio.create_task(worker()) for _ in range(3)]

    # Run the bot and workers concurrently
    await asyncio.gather(bot.infinity_polling(), *worker_tasks)

# Run bot
if __name__ == "__main__":
    asyncio.run(main())