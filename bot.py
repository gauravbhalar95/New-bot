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
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult  # ✅ Only this handler uses thumbnails & clips
from handlers.x_handler import download_twitter_media
from handlers.mega_handlers import MegaNZ  
from utils.logger import setup_logging
from utils.streaming import get_streaming_url, ApiVideoClient, download_best_clip

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
mega = MegaNZ()
download_queue = asyncio.Queue()

# Supported platforms and handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,  # ✅ Only this platform will use thumbnails & clip download
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
            return await handler(url)  # Attempt download
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(2)  # Wait before retrying
    return None  # Return None if all retries fail

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

        # Use retry function for more reliable downloads
        task = asyncio.create_task(retry_download(handler, url))
        result = await task

        if not result:
            await bot.send_message(message.chat.id, "❌ **Download failed after multiple attempts.**")
            return

        if isinstance(result, tuple) and len(result) >= 3:
            file_path, file_size, streaming_url = result[:3]
            thumbnail_path = result[3] if len(result) > 3 else None
        else:
            await bot.send_message(message.chat.id, "❌ **Error processing video.**")
            return

        # Debug: Check variable types
        logger.debug(f"Type of file_size: {type(file_size)}, Type of TELEGRAM_FILE_LIMIT: {type(TELEGRAM_FILE_LIMIT)}")

        # Convert file_size & TELEGRAM_FILE_LIMIT to integers
        file_size = int(file_size)
        telegram_limit = int(TELEGRAM_FILE_LIMIT)

        # If file is too large, generate a streaming link instead
        if not file_path or file_size > telegram_limit:
            video_url, duration = await get_streaming_url(url)

            # Debug: Check duration type
            logger.debug(f"Type of duration: {type(duration)}")

            if video_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Watch here:** [Click]({video_url})",
                    disable_web_page_preview=True
                )

                # ✅ Only extract best 1-minute clip if it's an adult video
                if handler == process_adult:
                    clip_path = await download_best_clip(video_url, int(duration))  # Convert duration to int
                    if clip_path:
                        async with aiofiles.open(clip_path, "rb") as clip:
                            await bot.send_video(message.chat.id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
                        os.remove(clip_path)
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        log_memory_usage()

        # ✅ Only send thumbnail if it's an adult video
        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # Send video file
        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        # Cleanup
        for path in [file_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# Worker function for parallel downloads
async def worker():
    """Processes multiple downloads in parallel (up to 3 at a time)."""
    while True:
        queue_items = []
        while not download_queue.empty() and len(queue_items) < 3:  # Process up to 3 downloads at once
            queue_items.append(await download_queue.get())

        if queue_items:
            tasks = [asyncio.create_task(background_download(msg, url)) for msg, url in queue_items]
            await asyncio.gather(*tasks)  # Run all tasks concurrently

            for _ in queue_items:
                download_queue.task_done()

# Start command
@bot.message_handler(commands=["start"])
async def start(message):
    """Sends a welcome message to the user when they start the bot."""
    user_name = message.from_user.first_name or "User"
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link or use `/meganz` to login to Mega.nz."
    await bot.reply_to(message, welcome_text)
    logger.info(f"User {message.chat.id} started the bot.")

# Handle incoming URLs
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles incoming messages and adds them to the download queue."""
    url = message.text.strip()
    await download_queue.put((message, url))
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")

# Main async function
async def main():
    """Starts the bot and runs the worker function in parallel."""
    logger.info("Bot is starting...")
    worker_task = asyncio.create_task(worker())  # Worker for parallel downloads
    await asyncio.gather(bot.infinity_polling(), worker_task)

# Run bot
if __name__ == "__main__":
    asyncio.run(main())