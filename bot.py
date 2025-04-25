import os
import gc
import logging
import asyncio
import aiofiles
import re
import httpx
import sys
import time
import psutil
import signal
from datetime import datetime, timezone
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from asyncio import Semaphore

# Import local modules
from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
    DEFAULT_ADMIN,
    ADMIN_IDS
)
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Constants for memory management
MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500MB
MAX_CONCURRENT_DOWNLOADS = 2
MAX_FILE_SIZE = 1024 * 1024 * 500  # 500MB
CLEANUP_INTERVAL = 300  # 5 minutes

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

# MEGA client setup
mega = None

# Active downloads tracking
active_downloads = set()
cleanup_tasks = set()

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

def get_current_utc():
    """Returns current UTC time in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

async def check_memory_usage():
    """Checks current memory usage and returns True if it's safe to proceed."""
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss
    return memory_usage < MAX_MEMORY_USAGE

async def cleanup_files():
    """Periodically cleans up temporary files and performs garbage collection."""
    while True:
        try:
            # Clean up temp directory
            temp_dir = "downloads"  # Adjust to your temp directory
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)
                    try:
                        if os.path.isfile(filepath) and time.time() - os.path.getctime(filepath) > 3600:
                            os.remove(filepath)
                    except Exception as e:
                        logger.error(f"[{get_current_utc()}] Error cleaning up file {filepath}: {e}")

            # Force garbage collection
            gc.collect()
            
            await asyncio.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"[{get_current_utc()}] Error in cleanup task: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"[{get_current_utc()}] Error sending message: {e}")

def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def get_mega_client():
    global mega
    if mega is None:
        try:
            m = Mega()
            logger.info(f"[{get_current_utc()}] Attempting MEGA login with email: {MEGA_EMAIL}")
            mega = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
            logger.info(f"[{get_current_utc()}] MEGA client initialized successfully")
        except Exception as e:
            logger.error(f"[{get_current_utc()}] Failed to initialize MEGA client: {e}", exc_info=True)
            return None
    return mega

async def upload_to_mega(file_path, filename):
    try:
        if not await check_memory_usage():
            logger.error(f"[{get_current_utc()}] Insufficient memory for MEGA upload")
            return None

        mega = await get_mega_client()
        if not mega:
            return None

        logger.info(f"[{get_current_utc()}] Uploading file to MEGA: {filename}")
        
        try:
            file = await asyncio.to_thread(mega.upload, file_path)
            if not file:
                return None

            share_link = await asyncio.to_thread(mega.get_upload_link, file)
            return share_link if isinstance(share_link, str) else None

        except Exception as upload_error:
            logger.error(f"[{get_current_utc()}] Error during upload: {upload_error}")
            return None

    except Exception as e:
        logger.error(f"[{get_current_utc()}] Unexpected error in upload_to_mega: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or MEGA."""
    download_id = f"{message.chat.id}_{int(time.time())}"
    
    try:
        # Check memory usage before proceeding
        if not await check_memory_usage():
            await send_message(message.chat.id, "⚠️ Server is currently under high load. Please try again later.")
            return

        # Add to active downloads
        active_downloads.add(download_id)

        async with download_semaphore:
            request_type = "Video Download"
            if is_audio:
                request_type = "Audio Download"
            elif is_video_trim:
                request_type = "Video Trimming"
            elif is_audio_trim:
                request_type = "Audio Trimming"

            await send_message(message.chat.id, f"📥 Processing your {request_type.lower()}...")
            
            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ Unsupported URL.")
                return

            # Process the download based on type
            try:
                if is_video_trim:
                    file_path, file_size = await process_video_trim(url, start_time, end_time)
                    file_paths = [file_path] if file_path else []
                elif is_audio_trim:
                    file_path, file_size = await process_audio_trim(url, start_time, end_time)
                    file_paths = [file_path] if file_path else []
                elif is_audio:
                    result = await extract_audio_ffmpeg(url)
                    file_paths = [result[0]] if isinstance(result, tuple) else [result]
                    file_size = result[1] if isinstance(result, tuple) and len(result) > 1 else None
                else:
                    result = await PLATFORM_HANDLERS[platform](url)
                    if isinstance(result, tuple):
                        file_paths = result[0] if isinstance(result[0], list) else [result[0]]
                        file_size = result[1] if len(result) > 1 else None
                    else:
                        file_paths = [result] if result else []
                        file_size = None

                if not file_paths:
                    await send_message(message.chat.id, "❌ Download failed. No media found.")
                    return

                for file_path in file_paths:
                    if not file_path or not os.path.exists(file_path):
                        continue

                    file_size = file_size or os.path.getsize(file_path)

                    if file_size > TELEGRAM_FILE_LIMIT:
                        mega_link = await upload_to_mega(file_path, os.path.basename(file_path))
                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"✅ File uploaded successfully!\n\n📥 Download from MEGA:\n{mega_link}"
                            )
                        else:
                            await send_message(
                                message.chat.id,
                                "❌ Upload failed. Please try again later."
                            )
                    else:
                        async with aiofiles.open(file_path, 'rb') as file:
                            content = await file.read()
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, content)
                            else:
                                await bot.send_video(message.chat.id, content, supports_streaming=True)

                    # Cleanup
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as cleanup_error:
                        logger.error(f"[{get_current_utc()}] Cleanup error: {cleanup_error}")

            except Exception as process_error:
                logger.error(f"[{get_current_utc()}] Processing error: {process_error}")
                await send_message(message.chat.id, f"❌ An error occurred: {str(process_error)}")

    except Exception as e:
        logger.error(f"[{get_current_utc()}] Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ An error occurred: {str(e)}")

    finally:
        # Remove from active downloads
        active_downloads.discard(download_id)
        gc.collect()



async def upload_to_gofile(file_path):
    try:
        # Step 1: Get server
        async with httpx.AsyncClient() as client:
            res = await client.get("https://api.gofile.io/getServer")
            server = res.json()["data"]["server"]

            # Step 2: Upload file
            upload_url = f"https://{server}.gofile.io/uploadFile"
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                response = await client.post(upload_url, files=files)

        data = response.json()
        if data['status'] == 'ok':
            return data['data']['downloadPage']
        else:
            logger.error(f"GoFile error: {data}")
            return "GoFile upload failed"
    except Exception as e:
        logger.error(f"GoFile upload error: {e}")
        return "Failed to upload to GoFile"



async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or Gofile."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")
        # Process the Instagram image
        try:
            result = await process_instagram_image(url)

            # Handle different return formats
            if isinstance(result, list):
                file_paths = result
            elif isinstance(result, tuple) and len(result) >= 2:
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
            else:
                file_paths = [result] if result else []

            if not file_paths or all(not path for path in file_paths):
                logger.warning("No valid image paths returned from Instagram handler")
                await send_message(message.chat.id, "❌ **Download failed. No images found.**")
                return

            # Process each image
            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Image path does not exist: {file_path}")
                    continue

                # Get file size
                file_size = os.path.getsize(file_path)

                # Handle case where file is too large for Telegram
                if file_size > TELEGRAM_FILE_LIMIT:
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    logger.info(f"Image too large for Telegram: {file_size} bytes. Using Gofile.")

                    # Upload to Gofile
                    gofile_link = await upload_to_gofile(file_path, filename)

                    if gofile_link:
                        logger.info(f"Successfully uploaded image to Gofile: {gofile_link}")
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from Gofile]({gofile_link})",
                            parse_mode="Markdown"
                        )
                    else:
                        logger.warning("Gofile upload failed")
                        await send_message(message.chat.id, "❌ **Image download failed.**")
                else:
                    # Send image to Telegram
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            await bot.send_photo(message.chat.id, file_content, timeout=60)
                            logger.info(f"Successfully sent image to Telegram")
                    except Exception as send_error:
                        logger.error(f"Error sending image to Telegram: {send_error}")
                        await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

                # Cleanup the file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up image file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image file {file_path}: {cleanup_error}")

            # Send success message
            await send_message(message.chat.id, "✅ **Instagram image(s) downloaded successfully!**")

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

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

@bot.message_handler(commands=["story"])
async def handle_story_request(message):
    """Handles Instagram story image download requests."""
    url = message.text.replace("/story", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide an Instagram story URL.")
        return

    if "/stories/" not in url or not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ Please provide a valid Instagram story URL.")
        return

    await send_message(message.chat.id, "📲 Instagram story detected! Fetching image(s)...")

    # Add to download queue
    await download_queue.put((message, url))
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

    # Check if URL is Instagram
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command only works with Instagram image URLs.**")
        return

    # Add to download queue
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