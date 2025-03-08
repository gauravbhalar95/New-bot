import os
import gc
import logging
import asyncio
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
from handlers.common_handler import process_adult  # ✅ Uses thumbnails & clips
from handlers.x_handler import download_twitter_media
from handlers.mega_handlers import MegaNZ  
from utils.logger import setup_logging
from utils.streaming import get_streaming_url

# ✅ Logging setup
logger = setup_logging(logging.DEBUG)

# ✅ Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
mega = MegaNZ()
download_queue = asyncio.Queue()

# ✅ Supported platforms and handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,  # ✅ Uses thumbnails & best scene clip
    ),
}

# ✅ Detect platform based on URL
def detect_platform(url):
    """Detects the platform and returns the handler function."""
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# ✅ Log memory usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024):.2f} MB")

# ✅ Function to extract a 1-minute highlight scene
async def download_best_clip(file_path, file_size):
    """Extracts a 1-minute best scene clip from the video."""
    clip_path = file_path.replace(".mp4", "_clip.mp4")
    start_time = max(0, (file_size // 4) // (1024 * 1024))  # Start at 1/4th of video

    command = [
        "ffmpeg", "-i", file_path, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "ultrafast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None

# ✅ Background download function
async def background_download(message, url):
    """Handles downloading & sending the video to Telegram."""
    try:
        await bot.send_message(message.chat.id, "📥 **Download started...**")
        logger.info(f"Processing URL: {url}")

        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # ✅ Fix: Pass full text if `process_adult`, otherwise just URL
        task = asyncio.create_task(handler(message.text)) if handler == process_adult else asyncio.create_task(handler(url))
        result = await task

        # ✅ Fix: Unpack 5 return values from `process_adult`
        if isinstance(result, tuple) and len(result) == 5:
            file_path, file_size, streaming_url, thumbnail_path, clip_path = result
        else:
            await bot.send_message(message.chat.id, "❌ **Error processing video.**")
            return

        # ✅ If file is too large, send a streaming link
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            video_url, duration = await get_streaming_url(url)
            if video_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Watch here:** [Click]({video_url})",
                    disable_web_page_preview=True
                )

                # ✅ Fix: Use file_path instead of video_url for best scene clip
                if handler == process_adult:
                    clip_path = await download_best_clip(file_path, file_size)
                    if clip_path:
                        with open(clip_path, "rb") as clip:
                            await bot.send_video(message.chat.id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
                        os.remove(clip_path)
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        log_memory_usage()

        # ✅ Fix: Send thumbnail if available
        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # ✅ Send full video
        with open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        # ✅ Fix: Cleanup all files
        for path in [file_path, thumbnail_path, clip_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# ✅ Worker function for parallel downloads
async def worker():
    while True:
        message, url = await download_queue.get()
        await background_download(message, url)
        download_queue.task_done()

# ✅ `/start` command
@bot.message_handler(commands=["start"])
async def start(message):
    user_name = message.from_user.first_name or "User"
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link or use `/meganz` to login to Mega.nz."
    await bot.reply_to(message, welcome_text)
    logger.info(f"User {message.chat.id} started the bot.")

# ✅ Handle incoming messages (URLs)
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    await download_queue.put((message, url))
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")

# ✅ Main async function
async def main():
    logger.info("Bot is starting...")
    worker_task = asyncio.create_task(worker())  # ✅ Worker for parallel downloads
    await asyncio.gather(bot.infinity_polling(), worker_task)

# ✅ Run bot
if __name__ == "__main__":
    asyncio.run(main())