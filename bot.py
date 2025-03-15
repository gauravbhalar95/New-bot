import os
import gc
import logging
import asyncio
import aiofiles
import requests
import telebot
import psutil
from queue import Queue
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg, extract_audio
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging
from utils.streaming import *

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Supported platforms and handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube, extract_audio),
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

        task = asyncio.create_task(handler(url))
        result = await task

        if isinstance(result, tuple):
            if len(result) == 3:
                file_path, file_size, download_url = result
            elif len(result) == 2:
                file_path, file_size = result
                download_url = None
            else:
                await bot.send_message(message.chat.id, "❌ **Error processing video.**")
                return

        # Handle M3U8 links by converting to MP4
        if file_path and file_path.endswith(".m3u8"):
            converted_path = file_path.replace(".m3u8", ".mp4")
            converted_path = await convert_m3u8_to_mp4(file_path, converted_path)
            if converted_path:
                file_path = converted_path
                file_size = os.path.getsize(file_path)

        # If file is too large, provide a direct download link instead
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            if download_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Download here:** [Click]({download_url})",
                    disable_web_page_preview=True
                )

                # ✅ Extract 1-minute clip if it's an adult video
                if handler == process_adult:
                    clip_path = await download_best_clip(download_url, file_size)
                    if clip_path:
                        async with aiofiles.open(clip_path, "rb") as clip:
                            await bot.send_video(message.chat.id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
                        os.remove(clip_path)
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        log_memory_usage()

        # ✅ Send thumbnail if available
        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # Send video file with increased timeout
        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True, timeout=600)

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
    while True:
        message, url = await download_queue.get()
        await background_download(message, url)
        download_queue.task_done()

# Start command
@bot.message_handler(commands=["start"])
async def start(message):
    user_name = message.from_user.first_name or "User"
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link to download."
    await bot.reply_to(message, welcome_text)
    logger.info(f"User {message.chat.id} started the bot.")

# Handle incoming URLs
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    await download_queue.put((message, url))
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")

# `/audio` Command for Audio Extraction
@bot.message_handler(commands=["audio"])
async def download_audio(message):
    url = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else None

    if not url:
        await bot.send_message(message.chat.id, "❌ **Please provide a valid YouTube URL.**")
        return

    await bot.send_message(message.chat.id, "🎵 **Extracting audio... Please wait.**")

    # ✅ Correctly call extract_audio_ffmpeg with the URL parameter
    audio_file, file_size = await extract_audio(url)

    if audio_file:
        async with aiofiles.open(audio_file, "rb") as audio:
            await bot.send_audio(message.chat.id, audio, caption="🎧 **Here's your MP3 file!**")
        os.remove(audio_file)
    else:
        await bot.send_message(message.chat.id, "❌ **Failed to extract audio.**")

# `/ping` Command for Checking Bot Status
@bot.message_handler(commands=["ping"])
async def ping(message):
    await bot.send_message(message.chat.id, "🏓 Pong!")
    logger.info("✅ Received /ping command.")

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