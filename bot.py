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
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

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

# M3U8 to MP4 conversion function
async def convert_m3u8_to_mp4(m3u8_url, output_path):
    command = [
        "ffmpeg", "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()

    if process.returncode == 0 and os.path.exists(output_path):
        return output_path
    return None

# Function to download a 1-minute best scene clip (Used only in `process_adult`)
async def download_best_clip(video_url, duration):
    """Extracts a 1-minute highlight scene from the video using FFmpeg."""
    clip_path = "best_scene.mp4"
    start_time = max(0, duration // 3)  # Start at 1/3rd of the video
    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "ultrafast", "-threads", "4", "-y", clip_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()

    if process.returncode == 0 and os.path.exists(clip_path):
        return clip_path
    return None

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

        if isinstance(result, tuple) and len(result) >= 3:
            file_path, file_size, download_url = result[:3]
            thumbnail_path = result[3] if len(result) > 3 else None
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

                # ✅ Only extract best 1-minute clip if it's an adult video
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