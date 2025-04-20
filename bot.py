import os
import gc
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from telebot.async_telebot import AsyncTeleBot

# Import local modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, MEGA_EMAIL, MEGA_PASSWORD
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# MEGA client setup
mega = Mega()
try:
    m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
    logger.info("Successfully logged in to MEGA")
except Exception as e:
    logger.error(f"Failed to login to MEGA: {e}")
    m = None

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
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def detect_platform(url):
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_mega(file_path, filename):
    try:
        if not m:
            logger.error("MEGA client not initialized")
            return None

        # Direct upload without folder
        file = m.upload(file_path)
        
        # Get upload link directly
        file_url = m.get_upload_link(file)
        return file_url

    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    try:
        request_type = "Video Download"
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"

        await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Process based on type
        if is_video_trim:
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []
            download_url = None

        elif is_audio_trim:
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []
            download_url = None

        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result
                file_paths = [file_path] if file_path else []
                download_url = None
            else:
                file_path, file_size, download_url = result, None, None
                file_paths = [file_path] if file_path else []

        else:
            if platform == "Instagram":
                if "/reel/" in url or "/tv/" in url:
                    result = await process_instagram(url)
                else:
                    result = await process_instagram_image(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            if isinstance(result, tuple) and len(result) >= 3:
                file_paths, file_size, download_url = result
                if not isinstance(file_paths, list):
                    file_paths = [file_paths]
            elif isinstance(result, tuple):
                file_paths, file_size = result
                if not isinstance(file_paths, list):
                    file_paths = [file_paths]
                download_url = None
            else:
                file_paths = [result] if isinstance(result, str) else result
                file_size = None
                download_url = None

        if not file_paths or all(not path for path in file_paths):
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue

            file_size = file_size or os.path.getsize(file_path)
            if file_size > TELEGRAM_FILE_LIMIT:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    await send_message(message.chat.id, f"⚠️ **File too large.**\n📥 [Download from MEGA]({mega_link})")
                elif download_url:
                    await send_message(message.chat.id, f"⚠️ **File too large.**\n📥 [Download link]({download_url})")
                else:
                    await send_message(message.chat.id, "❌ **File too large. MEGA upload failed.**")

            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        content = await file.read()
                        if len(content) > TELEGRAM_FILE_LIMIT:
                            raise ValueError("File exceeds Telegram limit")

                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, content, timeout=600)
                        else:
                            await bot.send_video(message.chat.id, content, supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"Send error: {send_error}")
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    mega_link = await upload_to_mega(file_path, filename)
                    if mega_link:
                        await send_message(message.chat.id, f"⚠️ **File too large.**\n📥 [Download from MEGA]({mega_link})")
                    else:
                        await send_message(message.chat.id, "❌ **Error sending file and MEGA upload failed.**")

            try:
                os.remove(file_path)
                logger.info(f"Deleted: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Cleanup error: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"Error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def process_image_download(message, url):
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")

        result = await process_instagram_image(url)
        if isinstance(result, list):
            file_paths = result
        elif isinstance(result, tuple):
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        else:
            file_paths = [result]

        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue

            size = os.path.getsize(file_path)
            if size > TELEGRAM_FILE_LIMIT:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                link = await upload_to_mega(file_path, filename)
                if link:
                    await send_message(message.chat.id, f"📸 **Image too large.**\n📥 [Download from MEGA]({link})")
                else:
                    await send_message(message.chat.id, "❌ **Image too large. Upload failed.**")
            else:
                async with aiofiles.open(file_path, "rb") as f:
                    content = await f.read()
                    await bot.send_photo(message.chat.id, content)

            os.remove(file_path)

        gc.collect()

    except Exception as e:
        logger.error(f"Image download error: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **Failed to download image:** `{e}`")

# Worker for parallel download tasks
async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        task = await download_queue.get()

        if len(task) == 2:
            # Image processing task
            message, url = task
            await process_image_download(message, url)
        else:
            # Regular download task
            message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
            await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)

        download_queue.task_done()

# Start/help command
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "I can help you download media from various platforms:\n"
        "• YouTube\n• Instagram\n• Facebook\n• Twitter/X\n\n"
        "Commands:\n"
        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio from video\n"
        "• /image <URL> - Download Instagram images\n"
        "• /trim <URL> <Start Time> <End Time> - Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> - Extract audio segment\n\n"
        "Examples:\n"
        "• /image https://instagram.com/p/example\n"
        "• /trim https://youtube.com/watch?v=example 00:01:00 00:02:30\n"
        "• /trimAudio https://youtube.com/watch?v=example 00:01:00 00:02:30"
    )
    await bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# Audio extraction handler
@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")

# Instagram image download handler
@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handles Instagram image download requests."""
    url = message.text.replace("/image", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide an Instagram image URL.")
        return

    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command only works with Instagram image URLs.**")
        return

    await download_queue.put((message, url))
    await send_message(message.chat.id, "🖼️ **Added to image download queue!**")

# Video trim handler
@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: /trim <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✂️🎬 **Added to video trimming queue!**")

# Audio trim handler
@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    """Handles audio segment extraction requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: /trimAudio <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️🎵 **Added to audio segment extraction queue!**")

# General message handler
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added to video download queue!")

# Main bot runner
async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)
    for _ in range(num_workers):
        asyncio.create_task(worker())

    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")

if __name__ == "__main__":
    asyncio.run(main())