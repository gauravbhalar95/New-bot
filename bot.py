#!/usr/bin/env python3

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

# MEGA.nz setup
mega = Mega()
mega_instance = None

# Initialize MEGA instance
def init_mega():
    global mega_instance
    try:
        if not MEGA_EMAIL or not MEGA_PASSWORD:
            logger.error("MEGA credentials not set")
            return False
        
        mega_instance = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("MEGA.nz login successful")
        return True
    except Exception as e:
        logger.error(f"MEGA.nz login failed: {e}")
        return False

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

async def upload_to_mega(file_path, filename):
    """
    Uploads a file to MEGA.nz and returns a shareable link.

    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in MEGA.nz

    Returns:
        str: Shareable link to the uploaded file
    """
    try:
        if not mega_instance:
            if not init_mega():
                return None

        # Create folder if it doesn't exist
        folder = mega_instance.find('telegram_uploads')
        if not folder:
            folder = mega_instance.create_folder('telegram_uploads')
        
        file = mega_instance.upload(file_path, folder[0])
        link = mega_instance.get_link(file)
        return link

    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or MEGA."""
    try:
        request_type = "Video Download"
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"

        await send_message(message.chat.id, f"📥 Processing your {request_type.lower()}...")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ Unsupported URL.")
            return

        # Handle request based on type
        if is_video_trim:
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []
        elif is_audio_trim:
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []
        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result
                file_paths = [file_path] if file_path else []
            else:
                file_paths = [result] if result else []
                file_size = None
        else:
            if platform == "Instagram":
                if "/reel/" in url or "/tv/" in url:
                    result = await process_instagram(url)
                else:
                    result = await process_instagram_image(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            # Handle different return formats
            if isinstance(result, tuple):
                if len(result) >= 2:
                    file_paths = result[0] if isinstance(result[0], list) else [result[0]]
                    file_size = result[1]
            else:
                file_paths = result if isinstance(result, list) else [result] if result else []
                file_size = None

        if not file_paths or all(not path for path in file_paths):
            await send_message(message.chat.id, "❌ Download failed. No media found.")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                continue

            file_size = file_size or os.path.getsize(file_path)

            if file_size > TELEGRAM_FILE_LIMIT:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    await send_message(
                        message.chat.id,
                        f"⚠️ File too large for Telegram.\n📥 Download from MEGA: {mega_link}"
                    )
                else:
                    await send_message(message.chat.id, "❌ Upload to MEGA failed.")
            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        content = await file.read()
                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, content, timeout=600)
                        else:
                            await bot.send_video(message.chat.id, content, supports_streaming=True, timeout=600)
                except Exception as e:
                    logger.error(f"Error sending file: {e}")
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    mega_link = await upload_to_mega(file_path, filename)
                    
                    if mega_link:
                        await send_message(
                            message.chat.id,
                            f"⚠️ File upload to Telegram failed.\n📥 Download from MEGA: {mega_link}"
                        )
                    else:
                        await send_message(message.chat.id, "❌ File upload failed.")

            # Cleanup
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to clean up file {file_path}: {e}")

        gc.collect()

    except Exception as e:
        logger.error(f"Error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ An error occurred: {str(e)}")

#[Rest of the code remains the same as in your original version, just replace Dropbox references with MEGA]

# Main bot runner
async def main():
    """Runs the bot and initializes worker processes."""
    # Initialize MEGA connection
    if not init_mega():
        logger.error("Failed to initialize MEGA. Exiting...")
        return

    num_workers = min(3, os.cpu_count() or 1)
    for _ in range(num_workers):
        asyncio.create_task(worker())

    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")

if __name__ == "__main__":
    asyncio.run(main())