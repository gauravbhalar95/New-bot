import os
import gc
import logging
import asyncio
import aiofiles
import requests
import telebot
import psutil
import subprocess
from telebot.async_telebot import AsyncTeleBot
from handlers.mega_handlers import login, download_from_url, upload_to_mega

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging
from utils.streaming import get_streaming_url

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Mega.nz instance
mega = Mega()
mega_client = None  # Stores logged-in Mega account

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

# Handle Mega.nz login
@bot.message_handler(commands=["meganz"])
async def meganz_login(message):
    global mega_client
    try:
        args = message.text.split()
        if len(args) != 3:
            await bot.send_message(message.chat.id, "⚠️ **Usage:** `/meganz <email> <password>`")
            return

        email, password = args[1], args[2]
        mega_client = mega.login(email, password)

        if mega_client:
            await bot.send_message(message.chat.id, "✅ **Mega.nz Login Successful!**")
        else:
            await bot.send_message(message.chat.id, "❌ **Mega.nz Login Failed!** Check credentials.")

    except Exception as e:
        logger.error(f"Mega.nz Login Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **Error:** `{e}`")

# Handle Mega.nz upload
@bot.message_handler(commands=["mega"])
async def mega_upload(message):
    global mega_client
    try:
        if not mega_client:
            await bot.send_message(message.chat.id, "❌ **Please login first using** `/meganz <email> <password>`")
            return

        args = message.text.split()
        if len(args) != 3:
            await bot.send_message(message.chat.id, "⚠️ **Usage:** `/mega <file_url> <folder_name>`")
            return

        file_url, folder_name = args[1], args[2]
        file_name = file_url.split("/")[-1]

        # Download file from the given URL
        file_path = f"./{file_name}"
        response = requests.get(file_url, stream=True)

        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)

            # Upload to Mega.nz
            mega_folder = mega_client.find(folder_name)
            if not mega_folder:
                mega_folder = mega_client.create_folder(folder_name)

            uploaded_file = mega_client.upload(file_path, mega_folder[0])
            file_link = mega_client.get_upload_link(uploaded_file)

            await bot.send_message(
                message.chat.id, 
                f"✅ **File Uploaded Successfully!**\n📥 **Download Link:** {file_link}"
            )

            # Cleanup
            os.remove(file_path)

        else:
            await bot.send_message(message.chat.id, "❌ **Failed to download file.**")

    except Exception as e:
        logger.error(f"Mega.nz Upload Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **Error:** `{e}`")

# Background download function
async def background_download(message, url):
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

        file_size = int(file_size) if file_size.isdigit() else 0

        if not file_path or file_size > TELEGRAM_FILE_LIMIT:
            video_url, _ = await get_streaming_url(url)
            if video_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚡ **File too large. Watch here:** [Click]({video_url})",
                    disable_web_page_preview=True
                )
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        log_memory_usage()

        if handler == process_adult and thumbnail_path and os.path.exists(thumbnail_path):
            async with aiofiles.open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")

        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

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
    welcome_text = f"👋 **Welcome {user_name}!**\n\nSend a video link or use `/meganz` to login to Mega.nz."
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
    worker_task = asyncio.create_task(worker())  
    await asyncio.gather(bot.infinity_polling(), worker_task)

# Run bot
if __name__ == "__main__":
    asyncio.run(main())