import os
import gc
import logging
import asyncio
import aiofiles
import telebot
import psutil
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult  
from handlers.x_handler import download_twitter_media
from handlers.mega_handlers import MegaNZ  
from utils.logger import setup_logging
from utils.streaming import get_streaming_url, download_best_clip

# ✅ Logging setup
logger = setup_logging(logging.DEBUG)

# ✅ Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
mega = MegaNZ()
download_queue = asyncio.Queue()

# ✅ Supported Platforms & Handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,  # ✅ Only this platform supports thumbnails & clip download
    ),
}

def detect_platform(url):
    """Detects the platform and returns the handler."""
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# ✅ Log Memory Usage
def log_memory_usage():
    memory = psutil.virtual_memory()
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024):.2f} MB")


# ✅ Background Download Function
async def background_download(message, url):
    """Handles the entire download process and sends the video to Telegram."""
    try:
        await bot.send_message(message.chat.id, "📥 **Processing your request...**")
        logger.info(f"Processing URL: {url}")

        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # ✅ Fetch Streaming URL First
        streaming_url = await get_streaming_url(url)
        if streaming_url:
            await bot.send_message(
                message.chat.id,
                f"⚡ **Watch here:** [Click]({streaming_url})",
                disable_web_page_preview=True
            )
            return

        # ✅ Process Video
        task = asyncio.create_task(handler(url))
        result = await task

        if isinstance(result, tuple) and len(result) == 6:
            file_path, file_size, streaming_url, download_url, thumbnail_path, clip_path = result
        else:
            await bot.send_message(message.chat.id, "❌ **Error processing video.**")
            return

        # ✅ If file is too large, provide a streaming or download link instead
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            if download_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large for Telegram. Download here:** [Click]({download_url})",
                    disable_web_page_preview=True
                )

            if handler == process_adult and clip_path:
                async with aiofiles.open(clip_path, "rb") as clip:
                    await bot.send_video(message.chat.id, clip, caption="🎞 **Best 1-Min Clip!**")
                os.remove(clip_path)

            return

        log_memory_usage()

        # ✅ Send Thumbnail if Available (Only for Adult Content)
        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        # ✅ Send the Video
        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        # ✅ Cleanup
        for path in [file_path, thumbnail_path, clip_path]:
            if path and os.path.exists(path):
                os.remove(path)

        log_memory_usage()
        gc.collect()

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")


# ✅ Worker Function for Parallel Downloads
async def worker():
    while True:
        message, url = await download_queue.get()
        await background_download(message, url)
        download_queue.task_done()

# ✅ Start Command
@bot.message_handler(commands=["start"])
async def start(message):
    user_name = message.from_user.first_name or "User"
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend me a video link or use `/meganz` to login to Mega.nz."
    await bot.reply_to(message, welcome_text)
    logger.info(f"User {message.chat.id} started the bot.")

# ✅ Handle Incoming URLs
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    await download_queue.put((message, url))
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")

# ✅ Main Async Function
async def main():
    logger.info("Bot is starting...")
    worker_task = asyncio.create_task(worker())  # Worker for parallel downloads
    await asyncio.gather(bot.infinity_polling(), worker_task)

# ✅ Run the Bot
if __name__ == "__main__":
    asyncio.run(main())