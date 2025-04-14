#!/usr/bin/env python3

import os
import gc
import time
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

# Import configuration
from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
    DOWNLOAD_DIR,
    TEMP_DIR,
    INSTAGRAM_USERNAME,
    INSTAGRAM_PASSWORD
)
from utils.logger import setup_logging
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image

# Constants
MAX_CONCURRENT_DOWNLOADS = 5
MAX_WORKERS = min(32, (os.cpu_count() or 1) * 4)
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
MAX_RETRIES = 3
RETRY_DELAY = 5

# Platform patterns
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

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Resource management
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# MEGA.nz setup
mega = Mega()
mega_instance = None

async def init_mega():
    """Initialize MEGA instance with retry mechanism."""
    global mega_instance
    for attempt in range(MAX_RETRIES):
        try:
            if not MEGA_EMAIL or not MEGA_PASSWORD:
                logger.error("MEGA credentials not set")
                return False

            mega_instance = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            logger.info("MEGA.nz login successful")
            return True
        except Exception as e:
            logger.error(f"MEGA.nz login attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return False

@lru_cache(maxsize=1000)
def detect_platform(url: str) -> str:
    """Detect platform from URL with caching."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def send_message(chat_id: int, text: str, retry: bool = True) -> bool:
    """Send message with retries."""
    for attempt in range(MAX_RETRIES if retry else 1):
        try:
            await bot.send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Error sending message (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return False

async def upload_to_mega(file_path: str, filename: str) -> str:
    """Upload file to MEGA with optimizations."""
    async with download_semaphore:
        try:
            if not mega_instance:
                if not await init_mega():
                    return None

            loop = asyncio.get_event_loop()
            
            # Find or create upload folder
            folder = mega_instance.find('telegram_uploads')
            if not folder:
                folder = mega_instance.create_folder('telegram_uploads')

            file_size = os.path.getsize(file_path)
            logger.info(f"Starting MEGA upload for {filename} ({file_size / (1024*1024):.2f} MB)")

            # Upload file in thread pool
            file = await loop.run_in_executor(
                thread_pool,
                lambda: mega_instance.upload(file_path, folder[0])
            )

            if not file:
                return None

            # Get link
            link = await loop.run_in_executor(
                thread_pool,
                lambda: mega_instance.get_link(file)
            )

            logger.info(f"MEGA upload successful for {filename}")
            return link

        except Exception as e:
            logger.error(f"MEGA upload error: {e}")
            if "not logged in" in str(e).lower():
                logger.info("Attempting to reinitialize MEGA connection...")
                if await init_mega():
                    return await upload_to_mega(file_path, filename)
            return None

async def chunked_read(file_path: str):
    """Read file in chunks efficiently."""
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(CHUNK_SIZE):
            yield chunk

async def send_large_file(message: Message, file_path: str, is_audio: bool = False) -> bool:
    """Send large files with progress updates."""
    try:
        if is_audio:
            send_method = bot.send_audio
        else:
            send_method = bot.send_video

        async with download_semaphore:
            chunks = []
            total_size = 0
            
            async for chunk in chunked_read(file_path):
                chunks.append(chunk)
                total_size += len(chunk)
                
                if len(chunks) % 10 == 0:
                    await send_message(
                        message.chat.id,
                        f"📤 Uploading: {total_size / (1024*1024):.1f}MB processed",
                        retry=False
                    )

            await send_method(
                message.chat.id,
                chunks[0] if len(chunks) == 1 else b''.join(chunks),
                timeout=600
            )
            return True
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        return False

async def cleanup_file(file_path: str):
    """Clean up file asynchronously."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up file: {file_path}")
            gc.collect()  # Force garbage collection after file cleanup
    except Exception as e:
        logger.error(f"Cleanup error for {file_path}: {e}")

async def process_and_send(message: Message, file_paths: list, is_audio: bool = False, is_image: bool = False):
    """Process and send files with optimizations."""
    if not file_paths:
        return

    for file_path in file_paths:
        if not file_path or not os.path.exists(file_path):
            continue

        try:
            file_size = os.path.getsize(file_path)
            
            if file_size > TELEGRAM_FILE_LIMIT:
                await send_message(
                    message.chat.id,
                    f"⏳ File is large ({file_size / (1024*1024):.2f} MB), uploading to MEGA..."
                )
                
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    await send_message(
                        message.chat.id,
                        f"✅ File too large for Telegram.\n📥 <a href='{mega_link}'>Download from MEGA</a>"
                    )
                else:
                    await send_message(message.chat.id, "❌ Upload to MEGA failed.")
            else:
                if not await send_large_file(message, file_path, is_audio=is_audio):
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    mega_link = await upload_to_mega(file_path, filename)
                    
                    if mega_link:
                        await send_message(
                            message.chat.id,
                            f"✅ Telegram upload failed.\n📥 <a href='{mega_link}'>Download from MEGA</a>"
                        )
                    else:
                        await send_message(message.chat.id, "❌ File upload failed.")

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            await send_message(message.chat.id, f"❌ Error: {str(e)}")
        finally:
            await cleanup_file(file_path)

async def process_media_download(url: str, is_audio: bool = False, is_video_trim: bool = False, 
                               is_audio_trim: bool = False, start_time: str = None, end_time: str = None):
    """Process media downloads based on URL and type."""
    try:
        # Handle trimming requests
        if is_video_trim:
            logger.info(f"Processing video trim: {url}, {start_time}-{end_time}")
            return await process_video_trim(url, start_time, end_time)

        if is_audio_trim:
            logger.info(f"Processing audio trim: {url}, {start_time}-{end_time}")
            return await process_audio_trim(url, start_time, end_time)

        # Handle audio extraction
        if is_audio:
            logger.info(f"Processing audio extraction: {url}")
            return await extract_audio_ffmpeg(url)

        # Handle regular media downloads
        platform = detect_platform(url)
        if not platform:
            raise ValueError("Unsupported platform")

        handler = PLATFORM_HANDLERS.get(platform)
        if not handler:
            raise ValueError(f"No handler for platform: {platform}")

        logger.info(f"Processing {platform} download: {url}")
        return await handler(url)

    except Exception as e:
        logger.error(f"Error in process_media_download: {e}", exc_info=True)
        raise

async def process_instagram_image(message: Message, url: str):
    """Process Instagram image downloads."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        
        # Initialize Instagram session if needed
        if not await init_instagram_session():
            await send_message(message.chat.id, "❌ Failed to initialize Instagram session")
            return

        # Download image(s)
        image_paths = await process_instagram_image(url)
        if not image_paths:
            await send_message(message.chat.id, "❌ Failed to download image(s)")
            return

        # Send images
        await process_and_send(message, image_paths, is_image=True)

    except Exception as e:
        logger.error(f"Error processing Instagram image: {e}")
        await send_message(message.chat.id, "❌ Error processing Instagram image")

async def process_media(message: Message, task: dict):
    """Process media downloads."""
    url = task['url']
    is_audio = task.get('is_audio', False)
    is_video_trim = task.get('is_video_trim', False)
    is_audio_trim = task.get('is_audio_trim', False)
    start_time = task.get('start_time')
    end_time = task.get('end_time')

    try:
        request_type = (
            "Audio Download" if is_audio else
            "Video Trimming" if is_video_trim else
            "Audio Trimming" if is_audio_trim else
            "Video Download"
        )

        await send_message(message.chat.id, f"⏳ Processing your {request_type.lower()}...")

        result = await process_media_download(
            url, is_audio, is_video_trim, is_audio_trim, start_time, end_time
        )

        if not result or (isinstance(result, tuple) and not result[0]):
            await send_message(message.chat.id, "❌ Failed to process media")
            return

        # Handle different return formats
        if isinstance(result, tuple):
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        elif isinstance(result, list):
            file_paths = result
        else:
            file_paths = [result]

        await process_and_send(message, file_paths, is_audio=is_audio)

    except Exception as e:
        logger.error(f"Error processing media: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ Error: {str(e)}")

async def worker():
    """Optimized worker function."""
    while True:
        try:
            task = await download_queue.get()
            async with download_semaphore:
                message = task['message']
                task_type = task['type']
                url = task['url']

                if task_type == "image":
                    await process_instagram_image(message, url)
                else:
                    await process_media(message, task)

        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            download_queue.task_done()
            if gc.get_count()[0] > 1000:
                gc.collect()

def create_directories():
    """Creates necessary directories if they don't exist."""
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info("Created necessary directories")
    except Exception as e:
        logger.error(f"Error creating directories: {e}")

async def main():
    """Enhanced main function."""
    try:
        # Create necessary directories
        create_directories()

        # Initialize MEGA
        if not await init_mega():
            logger.error("Failed to initialize MEGA. Exiting...")
            return

        # Initialize Instagram session
        if not await init_instagram_session():
            logger.warning("Failed to initialize Instagram session. Instagram features may be limited.")

        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(MAX_WORKERS)]
        
        # Start bot polling with reconnection
        while True:
            try:
                await bot.infinity_polling(timeout=60)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Main error: {e}")
    finally:
        # Cleanup
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        thread_pool.shutdown(wait=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")