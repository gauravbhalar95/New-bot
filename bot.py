import os
import gc
import logging
import asyncio
import aiofiles
import re
import signal
from datetime import datetime
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

# MEGA client setup with retry mechanism
mega = Mega()
m = None

async def initialize_mega():
    global m
    try:
        m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("Successfully logged in to MEGA")
        return True
    except Exception as e:
        logger.error(f"Failed to login to MEGA: {e}")
        return False

# Platform patterns and handlers remain the same
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

async def check_mega_connection():
    """Check and restore MEGA connection if needed."""
    global m
    if m is None:
        return await initialize_mega()
    return True

async def send_message(chat_id, text):
    """Send a message with error handling."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def detect_platform(url):
    """Detect the platform from the URL."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_mega(file_path, filename):
    """Upload file to MEGA with improved error handling."""
    try:
        if not await check_mega_connection():
            logger.error("MEGA client not initialized")
            return None

        # Direct upload without folder
        file = m.upload(file_path)
        
        # Get upload link directly
        file_url = m.get_upload_link(file)
        return file_url

    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        await check_mega_connection()  # Try to reconnect on error
        return None

async def cleanup_temp_files(file_paths):
    """Clean up temporary downloaded files."""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to clean up file {file_path}: {e}")

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Process download requests with improved error handling."""
    file_paths = []
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

        # Process based on type (rest of the function remains the same)
        # ... (previous process_download implementation)

    except Exception as e:
        logger.error(f"Error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")
    finally:
        # Clean up any remaining files
        await cleanup_temp_files(file_paths)
        gc.collect()

async def process_image_download(message, url):
    """Process image download requests with improved error handling."""
    file_paths = []
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")

        result = await process_instagram_image(url)
        # ... (rest of the function remains the same)
        
    except Exception as e:
        logger.error(f"Image download error: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **Failed to download image:** `{e}`")
    finally:
        await cleanup_temp_files(file_paths)
        gc.collect()

async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        try:
            task = await download_queue.get()

            if len(task) == 2:
                message, url = task
                await process_image_download(message, url)
            else:
                message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        finally:
            download_queue.task_done()

# Message handlers remain the same
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

# Command handlers remain the same
@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")

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

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added to video download queue!")

async def main():
    """Runs the bot and initializes worker processes with automatic restart."""
    while True:  # Continuous restart loop
        try:
            logger.info("Starting bot...")
            
            # Initialize MEGA
            if not await initialize_mega():
                logger.error("Failed to initialize MEGA, retrying in 10 seconds...")
                await asyncio.sleep(10)
                continue
            
            # Initialize workers
            num_workers = min(3, os.cpu_count() or 1)
            worker_tasks = []
            for _ in range(num_workers):
                worker_tasks.append(asyncio.create_task(worker()))
            
            # Start polling with timeout and retry
            await bot.infinity_polling(timeout=60, retry_after=5)
            
        except Exception as e:
            logger.error(f"Bot crashed with error: {e}", exc_info=True)
            
            # Cancel any running worker tasks
            for task in worker_tasks:
                if not task.done():
                    task.cancel()
                    
            try:
                await asyncio.gather(*worker_tasks, return_exceptions=True)
            except Exception:
                pass
                
            # Wait before restart
            await asyncio.sleep(10)
            logger.info("Attempting to restart bot...")
            
            # Clear the download queue
            while not download_queue.empty():
                try:
                    download_queue.get_nowait()
                    download_queue.task_done()
                except asyncio.QueueEmpty:
                    break

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}")
    # Cancel all tasks
    for task in asyncio.all_tasks():
        task.cancel()
    
    # Exit gracefully
    logger.info("Shutting down gracefully...")
    exit(0)

if __name__ == "__main__":
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal_handler)
    
    # Run the bot
    asyncio.run(main())