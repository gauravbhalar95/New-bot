import os
import gc
import logging
import asyncio
import aiofiles
import re
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_youtube_request
from utils.logger import setup_logging

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Regex patterns for different platforms
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Platform handlers
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def process_download(message, url, start_time=None, end_time=None, is_audio=False, is_trim_request=False):
    """Handles video/audio download and sends it to Telegram."""
    try:
        await send_message(message.chat.id, "📥 **Processing your request...**")
        logger.info(f"Processing URL: {url}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_audio:
            result = await extract_audio_ffmpeg(url)
        elif is_trim_request and platform == "YouTube":
            result = await process_youtube_request(url, start_time, end_time)
        else:
            result = await PLATFORM_HANDLERS[platform](url)

        # Process result
        if isinstance(result, tuple):
            file_path, file_size, download_url = result if len(result) == 3 else (*result, None)
        else:
            file_path, file_size, download_url = result, None, None

        # If file is too large for Telegram, send direct download link
        if not file_path or (file_size and file_size > TELEGRAM_FILE_LIMIT):
            if download_url:
                await send_message(
                    message.chat.id,
                    f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})"
                )
            else:
                await send_message(message.chat.id, "❌ **Download failed.**")
            return

        # Send file to Telegram
        async with aiofiles.open(file_path, "rb") as file:
            if is_audio:
                await bot.send_audio(message.chat.id, file, timeout=600)
            else:
                await bot.send_video(message.chat.id, file, supports_streaming=True, timeout=600)

        # Cleanup
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        message, url, start_time, end_time, is_audio, is_trim_request = await download_queue.get()
        await process_download(message, url, start_time, end_time, is_audio, is_trim_request)
        download_queue.task_done()

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ **Please provide a URL.**")
        return
    await download_queue.put((message, url, None, None, True, False))
    await send_message(message.chat.id, "✅ **Added to audio queue!**")

@bot.message_handler(commands=["trim"])
async def handle_trim_request(message):
    """Handles YouTube video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: `/trim <YouTube URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, start_time, end_time, False, True))
    await send_message(message.chat.id, "✂️ **Added to trimming queue!**")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, None, None, False, False))
    await send_message(message.chat.id, "✅ **Added to download queue!**")

async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)  # Limit workers based on CPU cores
    for _ in range(num_workers):
        asyncio.create_task(worker())  # Start workers in background
    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())