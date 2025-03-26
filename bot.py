import os
import gc
import logging
import asyncio
import aiofiles
import re
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram, extract_audio_instagram
from handlers.facebook_handlers import process_facebook, extract_audio_facebook
from handlers.common_handler import process_adult, extract_audio_adult
from handlers.x_handler import download_twitter_media, extract_audio_twitter
from utils.logger import setup_logging
from handlers.trim_handlers import process_youtube_request

# Initialize logging
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Define platform handlers
PLATFORM_HANDLERS = {
    "YouTube": {
        "pattern": re.compile(r"(youtube\.com|youtu\.be)"),
        "video": process_youtube,
        "audio": extract_audio_ffmpeg,
        "trim": process_youtube_request,
    },
    "Instagram": {
        "pattern": re.compile(r"instagram\.com"),
        "video": process_instagram,
        "audio": extract_audio_instagram,
    },
    "Facebook": {
        "pattern": re.compile(r"facebook\.com"),
        "video": process_facebook,
        "audio": extract_audio_facebook,
    },
    "Twitter/X": {
        "pattern": re.compile(r"(x\.com|twitter\.com)"),
        "video": download_twitter_media,
        "audio": extract_audio_twitter,
    },
    "Adult": {
        "pattern": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
        "video": process_adult,
        "audio": extract_audio_adult,
    },
}

def detect_platform(url, request_type="video"):
    """Detects the platform and returns the corresponding handler."""
    for platform, handlers in PLATFORM_HANDLERS.items():
        if handlers["pattern"].search(url):
            return platform, handlers.get(request_type)
    return None, None

async def send_message(chat_id, text):
    """Sends a message asynchronously with error handling."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def process_download(message, url, request_type="video"):
    """Handles downloading (video/audio) and sending files to Telegram."""
    try:
        await send_message(message.chat.id, f"📥 **Processing {request_type}...**")
        logger.info(f"Processing {request_type}: {url}")

        # Check if it's a YouTube trim request
        trim_match = re.search(r"(\S+)\s+(\d+)\s+(\d+)", url)
        if trim_match:
            url, start_time, end_time = trim_match.groups()
            request_type = "trim"
            start_time, end_time = int(start_time), int(end_time)

        # Detect platform & get the correct handler
        platform, handler = detect_platform(url, request_type)
        if not handler:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Process download request
        if request_type == "trim":
            result = await handler(url, start_time, end_time)
        else:
            result = await handler(url)

        # Extract result
        file_path, file_size, download_url = result if isinstance(result, tuple) else (result, None, None)

        # Handle large files
        if not file_path or (file_size and file_size > TELEGRAM_FILE_LIMIT):
            if download_url:
                await send_message(message.chat.id, f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})")
            else:
                await send_message(message.chat.id, "❌ **Download failed.**")
            return

        # Send video/audio file
        async with aiofiles.open(file_path, "rb") as file:
            if request_type == "audio":
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
    """Worker function for processing downloads."""
    while True:
        message, url, request_type = await download_queue.get()
        asyncio.create_task(process_download(message, url, request_type))
        download_queue.task_done()

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ **Please provide a URL.**")
        return
    await download_queue.put((message, url, "audio"))
    await send_message(message.chat.id, "✅ **Added to audio queue!**")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general download requests (video)."""
    url = message.text.strip()
    await download_queue.put((message, url, "video"))
    await send_message(message.chat.id, "✅ **Added to download queue!**")

async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)  # Limit workers based on CPU cores
    for _ in range(num_workers):
        asyncio.create_task(worker())  # Start workers in background
    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())