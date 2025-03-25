import os
import gc
import logging
import asyncio
import aiofiles
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging
from handlers.trim_handlers import process_youtube_request

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Precompile regex patterns for faster matching
PLATFORM_PATTERNS = {
    "YouTube": (re.compile(r"(youtube\.com|youtu\.be)"), process_youtube, process_youtube_request),
    "Instagram": (re.compile(r"instagram\.com"), process_instagram),
    "Facebook": (re.compile(r"facebook\.com"), process_facebook),
    "Twitter/X": (re.compile(r"(x\.com|twitter\.com)"), download_twitter_media),
    "Adult": (re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"), process_adult),
}

def detect_platform(url, is_trim_request=False):
    """Efficiently detects the platform using regex matching."""
    for platform, (pattern, handler, *trim_handler) in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform, trim_handler[0] if is_trim_request and trim_handler else handler
    return None, None

async def send_message(chat_id, text):
    """Sends a message asynchronously, with error handling."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def background_download(message, url):
    """Handles the entire download process and sends the video to Telegram."""
    try:
        await send_message(message.chat.id, "📥 **Download started...**")
        logger.info(f"Processing URL: {url}")

        # Extract start & end time from URL format: "url start end"
        time_match = re.search(r"(\S+)\s+(\d+)\s+(\d+)", url)
        start_time, end_time = None, None
        is_trim_request = False

        if time_match:
            url, start_time, end_time = time_match.groups()
            start_time, end_time = int(start_time), int(end_time)
            is_trim_request = True

        platform, handler = detect_platform(url, is_trim_request)
        if not handler:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Process request based on platform
        if platform == "YouTube" and is_trim_request:
            logger.info(f"Trimming YouTube video: Start={start_time}s, End={end_time}s")
            result = await process_youtube_request(url, start_time, end_time)
        else:
            result = await handler(url)

        if isinstance(result, tuple):
            file_path, file_size, download_url = result if len(result) == 3 else (*result, None)

        # If file is too large, provide a direct download link instead
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            if download_url:
                await send_message(
                    message.chat.id,
                    f"⚠️ **The video is too large for Telegram.**\n📥 [Download here]({download_url})"
                )
            else:
                await send_message(message.chat.id, "❌ **Download failed.**")
            return

        # Send video file with increased timeout
        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True, timeout=600)

        # Cleanup
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def worker():
    """Worker function for parallel downloads."""
    while True:
        message, url = await download_queue.get()
        asyncio.create_task(background_download(message, url))
        download_queue.task_done()

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles incoming URLs and adds them to the download queue."""
    url = message.text.strip()
    await download_queue.put((message, url))
    await send_message(message.chat.id, "✅ **Added to download queue!**")

async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)  # Limit workers based on CPU cores
    for _ in range(num_workers):
        asyncio.create_task(worker())  # Start workers in background
    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())