#!/usr/bin/env python3

import os
import gc
import logging
import asyncio
import aiofiles
import re
import aiohttp
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from functools import lru_cache, partial
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

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

# Constants
MAX_CONCURRENT_DOWNLOADS = 5
MAX_WORKERS = min(32, (os.cpu_count() or 1) * 4)
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
MAX_RETRIES = 3
RETRY_DELAY = 5

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Connection and resource management
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

class ConnectionPool:
    def __init__(self):
        self.session = None
        self._lock = asyncio.Lock()
    
    async def get_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=300)
            connector = aiohttp.TCPConnector(limit=100, force_close=False)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
        return self.session
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

pool = ConnectionPool()

# MEGA.nz setup with retry mechanism
mega = Mega()
mega_instance = None

@asynccontextmanager
async def get_mega():
    global mega_instance
    for attempt in range(MAX_RETRIES):
        try:
            if not mega_instance:
                if not MEGA_EMAIL or not MEGA_PASSWORD:
                    logger.error("MEGA credentials not set")
                    yield None
                    return
                
                mega_instance = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
                logger.info("MEGA.nz login successful")
            
            yield mega_instance
            break
        except Exception as e:
            logger.error(f"MEGA.nz login attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                mega_instance = None
            else:
                yield None

# Platform patterns with caching
@lru_cache(maxsize=1000)
def detect_platform(url):
    """Cached platform detection."""
    PLATFORM_PATTERNS = {
        "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
        "Instagram": re.compile(r"instagram\.com"),
        "Facebook": re.compile(r"facebook\.com"),
        "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
        "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
    }
    
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def send_message(chat_id, text, retry=True):
    """Enhanced message sending with retry."""
    for attempt in range(MAX_RETRIES if retry else 1):
        try:
            await bot.send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Error sending message (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return False

async def chunked_read(file_path):
    """Efficient chunked file reading."""
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(CHUNK_SIZE):
            yield chunk

async def upload_to_mega(file_path, filename):
    """Enhanced MEGA upload with retries and progress tracking."""
    async with download_semaphore:
        async with get_mega() as mega:
            if not mega:
                return None

            try:
                # Use thread pool for CPU-bound operations
                loop = asyncio.get_event_loop()
                
                # Find or create upload folder
                folder = await loop.run_in_executor(
                    thread_pool,
                    lambda: mega.find('telegram_uploads') or mega.create_folder('telegram_uploads')
                )

                # Upload file
                upload_func = partial(mega.upload, file_path, folder[0])
                file = await loop.run_in_executor(thread_pool, upload_func)
                
                # Get link
                get_link_func = partial(mega.get_link, file)
                link = await loop.run_in_executor(thread_pool, get_link_func)
                
                return link

            except Exception as e:
                logger.error(f"MEGA upload error: {e}")
                return None

async def send_large_file(message, file_path, is_audio=False):
    """Optimized large file sending."""
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
                
                # Send progress updates periodically
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

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Enhanced download processor with optimizations."""
    async with download_semaphore:
        try:
            request_type = ("Audio Download" if is_audio else
                          "Video Trimming" if is_video_trim else
                          "Audio Trimming" if is_audio_trim else
                          "Video Download")

            await send_message(message.chat.id, f"📥 Processing your {request_type.lower()}...")
            
            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ Unsupported URL.")
                return

            # Process specific handler
            handler_task = asyncio.create_task(
                PLATFORM_HANDLERS[platform](url) if platform in PLATFORM_HANDLERS
                else process_instagram_image(url) if platform == "Instagram" and "/reel/" not in url and "/tv/" not in url
                else process_instagram(url)
            )

            result = await handler_task

            # Process results
            if not result:
                await send_message(message.chat.id, "❌ Download failed.")
                return

            file_paths = []
            file_size = None

            # Handle different return formats
            if isinstance(result, tuple):
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
                file_size = result[1]
            else:
                file_paths = result if isinstance(result, list) else [result]

            # Process each file
            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    continue

                current_size = file_size or os.path.getsize(file_path)

                if current_size > TELEGRAM_FILE_LIMIT:
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
                    if not await send_large_file(message, file_path, is_audio=is_audio or is_audio_trim):
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        mega_link = await upload_to_mega(file_path, filename)
                        
                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ File upload to Telegram failed.\n📥 Download from MEGA: {mega_link}"
                            )
                        else:
                            await send_message(message.chat.id, "❌ File upload failed.")

                # Cleanup in background
                asyncio.create_task(cleanup_file(file_path))

        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ Error: {str(e)}")

async def cleanup_file(file_path):
    """Asynchronous file cleanup."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error for {file_path}: {e}")

async def worker():
    """Enhanced worker with optimizations."""
    while True:
        try:
            async with download_semaphore:
                task = await download_queue.get()
                
                loop = asyncio.get_event_loop()
                if len(task) == 2:
                    await loop.run_in_executor(
                        thread_pool,
                        partial(process_image_download, *task)
                    )
                else:
                    await loop.run_in_executor(
                        thread_pool,
                        partial(process_download, *task)
                    )

                download_queue.task_done()
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            # Explicit garbage collection for large files
            if gc.get_count()[0] > 1000:
                gc.collect()

#[Previous command handlers remain the same...]

async def main():
    """Enhanced main function with proper cleanup."""
    try:
        # Initialize workers
        workers = [asyncio.create_task(worker()) for _ in range(MAX_WORKERS)]
        
        # Start bot polling with reconnection handling
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
        await pool.close()
        thread_pool.shutdown(wait=True)

if __name__ == "__main__":
    asyncio.run(main())