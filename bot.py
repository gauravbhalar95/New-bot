import os
import gc
import logging
import asyncio
import aiofiles
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
from utils.streaming import get_streaming_url

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

# Function to upload file to MediaFire using rclone
async def upload_to_mediafire(file_path):
    """Uploads a file to MediaFire and returns the public link."""
    remote_path = "mediafire:MyBotUploads/"  # Replace with your MediaFire rclone path
    command = ["rclone", "copy", file_path, remote_path]
    
    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        # Get the public download link
        link_command = ["rclone", "link", f"{remote_path}{os.path.basename(file_path)}"]
        link_process = await asyncio.create_subprocess_exec(*link_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        link_stdout, _ = await link_process.communicate()
        return link_stdout.decode().strip() if link_process.returncode == 0 else None
    
    return None

# Background download function
async def background_download(message, url):
    """Handles the entire download process and sends the video to Telegram or MediaFire."""
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
            file_path, file_size, streaming_url = result[:3]
            thumbnail_path = result[3] if len(result) > 3 else None
        else:
            await bot.send_message(message.chat.id, "❌ **Error processing video.**")
            return

        # ✅ Upload to MediaFire if file is too large
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            mediafire_link = await upload_to_mediafire(file_path)
            if mediafire_link:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Download here:** [Click]({mediafire_link})",
                    disable_web_page_preview=True
                )
            else:
                await bot.send_message(message.chat.id, "❌ **Upload to MediaFire failed.**")
            return

        log_memory_usage()

        # ✅ Only send thumbnail if it's an adult video
        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # ✅ Send video file directly to Telegram
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
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link or use `/meganz` to login to Mega.nz."
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
    logger.info("Bot is starting...")
    worker_task = asyncio.create_task(worker())  # Worker for parallel downloads
    await asyncio.gather(bot.infinity_polling(), worker_task)

# Run bot
if __name__ == "__main__":
    asyncio.run(main())