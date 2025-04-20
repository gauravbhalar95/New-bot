import os
import gc
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from dotenv import load_dotenv
import json
import time
from datetime import datetime

# Load environment variables
load_dotenv()

# Import local modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT
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

# MEGA setup with retry mechanism
class MegaHandler:
    def __init__(self):
        self.mega = None
        self.m = None
        self.last_attempt = 0
        self.retry_interval = 300  # 5 minutes
        self.initialize_mega()

    def initialize_mega(self):
        current_time = time.time()
        if current_time - self.last_attempt < self.retry_interval:
            return False

        self.last_attempt = current_time
        try:
            self.mega = Mega()
            email = os.getenv('MEGA_EMAIL')
            password = os.getenv('MEGA_PASSWORD')

            if not email or not password:
                logger.warning("MEGA credentials not set in environment variables")
                return False

            try:
                self.m = self.mega.login(email, password)
                logger.info("Successfully logged in to MEGA")
                return True
            except json.decoder.JSONDecodeError as e:
                logger.error(f"MEGA API response error: {e}")
                return False
            except Exception as e:
                logger.error(f"MEGA login error: {e}")
                return False

        except Exception as e:
            logger.error(f"MEGA initialization error: {e}")
            return False

    async def upload_file(self, file_path, filename):
        """Upload file to MEGA with retry mechanism"""
        if not self.m and not self.initialize_mega():
            return None

        try:
            file = self.m.upload(file_path)
            return self.m.get_link(file)
        except Exception as e:
            logger.error(f"MEGA upload error: {e}")
            return None

# Initialize MEGA handler
mega_handler = MegaHandler()

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
    """Sends a message asynchronously with error handling."""
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

async def handle_large_file(message, file_path, file_size, download_url=None):
    """Handles large files with fallback options."""
    try:
        # First attempt: MEGA upload
        mega_link = await mega_handler.upload_file(file_path, 
                                                 f"{message.chat.id}_{os.path.basename(file_path)}")
        
        if mega_link:
            await send_message(
                message.chat.id,
                f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
            )
            return True
        
        # Fallback: Direct download link if available
        if download_url:
            await send_message(
                message.chat.id,
                f"⚠️ **File too large for Telegram.**\n📥 [Direct download link]({download_url})"
            )
            return True
        
        # Final fallback
        await send_message(
            message.chat.id,
            "❌ **File too large and cloud upload failed. Please try again later.**"
        )
        return False
        
    except Exception as e:
        logger.error(f"Error handling large file: {e}")
        return False

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or cloud storage."""
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

        # Detect and validate platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Process the request based on type
        try:
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
                    file_path, file_size = result if len(result) == 2 else (result[0], None)
                    file_paths = [file_path] if file_path else []
                    download_url = None
                else:
                    file_paths = [result] if result else []
                    file_size = None
                    download_url = None
            else:
                # Handle platform-specific downloads
                result = await PLATFORM_HANDLERS[platform](url)
                if isinstance(result, tuple):
                    if len(result) >= 3:
                        file_paths, file_size, download_url = result
                    else:
                        file_paths, file_size = result
                        download_url = None
                    if not isinstance(file_paths, list):
                        file_paths = [file_paths] if file_paths else []
                else:
                    file_paths = result if isinstance(result, list) else [result] if result else []
                    file_size = None
                    download_url = None

        except Exception as e:
            logger.error(f"Error processing {request_type}: {e}")
            await send_message(message.chat.id, f"❌ **Error processing your request:** `{str(e)}`")
            return

        # Validate results
        if not file_paths or all(not path for path in file_paths):
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        # Process each file
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                continue

            try:
                if file_size is None:
                    file_size = os.path.getsize(file_path)

                if file_size > TELEGRAM_FILE_LIMIT:
                    await handle_large_file(message, file_path, file_size, download_url)
                else:
                    # Send file through Telegram
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        try:
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, file_content, timeout=600)
                            else:
                                await bot.send_video(message.chat.id, file_content, 
                                                   supports_streaming=True, timeout=600)
                        except Exception as send_error:
                            if "413" in str(send_error):
                                await handle_large_file(message, file_path, file_size, download_url)
                            else:
                                raise send_error

            finally:
                # Cleanup
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{str(e)}`")

async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or cloud storage."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")

        try:
            result = await process_instagram_image(url)
            
            if isinstance(result, list):
                file_paths = result
            elif isinstance(result, tuple) and len(result) >= 2:
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
            else:
                file_paths = [result] if result else []

            if not file_paths or all(not path for path in file_paths):
                await send_message(message.chat.id, "❌ **Download failed. No images found.**")
                return

            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    continue

                file_size = os.path.getsize(file_path)

                if file_size > TELEGRAM_FILE_LIMIT:
                    await handle_large_file(message, file_path, file_size)
                else:
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            await bot.send_photo(message.chat.id, file_content, timeout=60)
                    except Exception as send_error:
                        logger.error(f"Error sending image: {send_error}")
                        await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image file {file_path}: {cleanup_error}")

            await send_message(message.chat.id, "✅ **Instagram image(s) downloaded successfully!**")

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred:** `{str(e)}`")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{str(e)}`")

# Worker for parallel download tasks
async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        task = await download_queue.get()
        try:
            if len(task) == 2:
                message, url = task
                await process_image_download(message, url)
            else:
                message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            download_queue.task_done()

# Command handlers
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
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]
    
    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        for w in workers:
            w.cancel()

if __name__ == "__main__":
    asyncio.run(main())